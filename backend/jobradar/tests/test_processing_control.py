import threading
import time

from jobradar.services import processing_control as processing


def wait_for(predicate):
    deadline = time.monotonic() + 3
    while not predicate():
        assert time.monotonic() < deadline
        time.sleep(.01)


def test_pause_drains_active_unit_and_preserves_pending(tmp_path, monkeypatch):
    monkeypatch.setenv('DACHAPPLY_CONTROL_DB', str(tmp_path / 'control.sqlite3'))
    control = processing.store()
    started, release = threading.Event(), threading.Event()
    results = []

    @processing.durable('test-unit')
    def work(number):
        started.set()
        release.wait(3)
        results.append(number)

    first = threading.Thread(target=work, args=(1,))
    first.start()
    assert started.wait(3)
    control.mode('paused')
    second = threading.Thread(target=work, args=(2,))
    second.start()
    wait_for(lambda: control.status()['remaining_jobs'] == 1)
    assert control.status()['processing'] == 'pausing'
    release.set()
    first.join(3)
    assert results == [1]
    assert control.status()['processing'] == 'paused'
    assert control.status()['remaining_jobs'] == 1
    control.mode('running')
    second.join(3)
    assert results == [1, 2]
    assert control.status()['completed_jobs'] == 2


def test_concurrent_duplicate_admission_and_stop(tmp_path):
    control = processing.Store(tmp_path / 'control.sqlite3')
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=8) as executor:
        admitted = list(executor.map(lambda _: control.enqueue('pipeline', {'args': [1, 2]}), range(16)))
    assert len([unit for unit in admitted if unit]) == 1
    identity = next(unit for unit in admitted if unit)
    control.mode('stopping')
    assert not control.claim(identity, 'pipeline', 1)
    assert control.status()['processing'] == 'stopping'
    assert control.status()['remaining_jobs'] == 1


def test_restart_keeps_pause_pending_and_uncertain_work(tmp_path):
    path = tmp_path / 'control.sqlite3'
    control = processing.Store(path)
    pending = control.enqueue('mailbox', {'args': [], 'kwargs': {'force': True}})
    active = control.enqueue('pipeline', {'args': [1, 2], 'kwargs': {}})
    assert control.claim(active, 'pipeline', 1)
    control.mode('paused')
    restarted = processing.Store(path)
    assert restarted.recover() == [(pending, 'mailbox', '{"args":[],"kwargs":{"force":true}}')]
    assert restarted.status()['interrupted_jobs'] == 1
    assert restarted.status()['processing'] == 'paused'


def test_pipeline_and_daily_documents_share_admission_lane(tmp_path):
    control = processing.Store(tmp_path / 'control.sqlite3')
    pipeline = control.enqueue('pipeline', {'args': [1, 2]})
    document = control.enqueue('daily-document', {'args': [3, 2]})
    assert control.claim(pipeline, 'pipeline', 1)
    assert not control.claim(document, 'daily-document', 1)
    control.mode('paused')
    control.finish(pipeline)
    assert not control.claim(document, 'daily-document', 1)
    control.mode('running')
    assert control.claim(document, 'daily-document', 1)


def test_failed_units_are_visible_without_payload(tmp_path, monkeypatch):
    monkeypatch.setenv('DACHAPPLY_CONTROL_DB', str(tmp_path / 'control.sqlite3'))

    @processing.durable('test-failure')
    def fail():
        raise ValueError('secret-message')

    import pytest
    with pytest.raises(ValueError):
        fail()
    state = processing.store().status()
    assert state['failed_jobs'] == 1
    assert 'secret-message' not in str(state)


def test_long_pause_does_not_expire_document_task(monkeypatch):
    from jobradar.services import cv_tasks
    monkeypatch.setattr(cv_tasks, '_tasks', {
        'pending': {'status': 'queued', 'updated_at': 0},
        'active': {'status': 'running', 'updated_at': 0},
        'finished': {'status': 'ready', 'updated_at': 0},
    })
    cv_tasks._cleanup()
    assert set(cv_tasks._tasks) == {'pending', 'active'}


def test_document_snapshot_restores_binary_input_and_callback_once(tmp_path, monkeypatch):
    from jobradar.services import application_prep, cv_tasks
    monkeypatch.setenv('DACHAPPLY_CONTROL_DB', str(tmp_path / 'control.sqlite3'))
    monkeypatch.setattr(cv_tasks, '_tasks', {'fixture-task': {'id': 'fixture-task', 'status': 'queued',
        'updated_at': time.time(), '_cancel': threading.Event(), 'archive': None, '_estimate_key': ('fixture',)}})
    monkeypatch.setattr(application_prep, '_running', 0)
    results = []
    monkeypatch.setattr(application_prep, '_finish', lambda *args: results.append(args))
    from functools import partial
    finished = partial(application_prep._finish, 1, 2, 'cv-en')
    def fixture(task_id, correction_image, cancel_event, on_finish):
        pass
    control, identity, kind, payload, live = processing.admit_document(processing.store(), 'documents', fixture,
        ('fixture-task', (b'private-image', '.png'), threading.Event(), finished), {})
    assert identity
    restored = processing.restore_document(payload)
    assert restored['correction_image'] == [b'private-image', '.png']
    assert isinstance(restored['cancel_event'], threading.Event)
    restored['on_finish']('fixture-task')
    assert results == [(1, 2, 'cv-en', 'fixture-task')]
    assert application_prep._running == 1


def test_adjustment_callback_restores_without_taking_preparation_slot(monkeypatch):
    from jobradar.services import application_prep, cv_tasks
    monkeypatch.setattr(application_prep, '_running', 0)
    monkeypatch.setattr(cv_tasks, '_tasks', {})
    results = []
    monkeypatch.setattr(application_prep, '_adjusted', lambda *args: results.append(args))
    payload = {'document': {'task_id': 'adjustment'}, 'snapshot': {},
               'finish': {'action': 'adjusted', 'job_id': 1, 'user_id': 2, 'key': 'cv-en'}}
    restored = processing.restore_document(payload)
    restored['on_finish']('adjustment')
    assert results == [(1, 2, 'cv-en', 'adjustment')]
    assert application_prep._running == 0
