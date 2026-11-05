import json
from jobradar.services import processing_control as processing


def test_idle_ticks_and_restart_never_become_jobs(tmp_path):
    path = tmp_path / 'control.sqlite3'
    control = processing.Store(path)
    for kind in ('daily-tick', 'mailbox-tick'):
        unit = control.enqueue(kind, {'args': [], 'kwargs': {}})
        assert control.claim(unit, kind, 1)
        control.finish(unit)
    control.enqueue('daily-tick', {'args': [], 'kwargs': {}})
    control.mode('paused')
    control = processing.Store(path)
    control.recover()
    state = control.status()
    assert state['completed_jobs'] == state['remaining_jobs'] == 0
    assert state['total_jobs'] is None


def test_two_analyses_five_documents_count_once(tmp_path):
    control = processing.Store(tmp_path / 'control.sqlite3')
    for kind, count in [('daily-tick', 1), ('mailbox-tick', 1), ('pipeline', 2), ('daily-document', 5), ('documents', 5)]:
        for number in range(count):
            unit = control.enqueue(kind, {'args': [number, 2]})
            control.finish(unit)
    assert control.status()['completed_jobs'] == 7
    assert control.status()['total_jobs'] is None


def test_hidden_units_still_drain_before_stop(tmp_path):
    control = processing.Store(tmp_path / 'control.sqlite3')
    unit = control.enqueue('daily-document', {'args': [1, 2]})
    assert control.claim(unit, 'daily-document', 1)
    control.mode('stopping')
    assert control.status()['running_jobs'] == 0
    assert control.status()['processing'] == 'draining'
    assert control.active_units() == 1
    control.finish(unit)
    assert control.status()['processing'] == 'stopping'


def document(task, user=2, key='cv-en'):
    return {'document': {'task_id': task}, 'finish': {'action': 'finish', 'job_id': 1, 'user_id': user, 'key': key}}


def test_successful_retry_resolves_only_matching_interruption(tmp_path):
    control = processing.Store(tmp_path / 'control.sqlite3')
    for payload in [document('lost'), document('other-owner', 3), document('other-variant', key='cv-de')]:
        unit = control.enqueue('documents', payload)
        control.finish(unit, 'interrupted')
    retry = control.enqueue('documents', document('failed-retry'))
    control.finish(retry, 'failed')
    assert control.status()['interrupted_jobs'] == 3
    retry = control.enqueue('documents', document('successful-retry'))
    control.finish(retry)
    assert control.status()['interrupted_jobs'] == 2
    with control.connect() as db:
        resolved = db.execute("SELECT payload FROM units WHERE state='resolved'").fetchall()
    assert resolved == [('{}',)]


def test_existing_control_database_upgrades_without_losing_pending(tmp_path):
    import sqlite3
    path = tmp_path / 'old.sqlite3'
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE units (id TEXT PRIMARY KEY,kind TEXT,payload TEXT,state TEXT,created REAL)')
        db.executemany('INSERT INTO units VALUES (?,?,?,?,?)', [
            ('tick', 'daily-tick', '{}', 'completed', 1),
            ('lost', 'documents', json.dumps(document('lost')), 'interrupted', 2)])
    control = processing.Store(path)
    retry = control.enqueue('documents', document('retry'))
    control.finish(retry)
    assert control.status()['completed_jobs'] == 1
    assert control.status()['interrupted_jobs'] == 0


def test_no_work_result_is_not_a_completed_mailbox_job(tmp_path, monkeypatch):
    from types import SimpleNamespace
    control = processing.Store(tmp_path / 'control.sqlite3')
    for result in (None, (None, None), SimpleNamespace(skipped=True, error='')):
        monkeypatch.setitem(processing._handlers, 'mailbox-tick', lambda **kwargs: result)
        unit = control.enqueue('mailbox-tick', {'args': [], 'kwargs': {'force': True}})
        processing.execute(control, unit, 'mailbox-tick', [], {'force': True})
    assert control.status()['completed_jobs'] == 0


def test_pipeline_retry_identity_ignores_retry_options(tmp_path):
    control = processing.Store(tmp_path / 'control.sqlite3')
    lost = control.enqueue('pipeline', {'args': [1, 2], 'kwargs': {'reanalyse': ''}})
    control.finish(lost, 'interrupted')
    retry = control.enqueue('pipeline', {'args': [1, 2], 'kwargs': {'reanalyse': 'retry'}})
    control.finish(retry)
    assert control.status()['interrupted_jobs'] == 0
