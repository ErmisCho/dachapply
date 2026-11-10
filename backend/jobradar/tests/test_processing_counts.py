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
    unit = control.enqueue('daily-tick', {'args': [], 'kwargs': {}})
    assert control.claim(unit, 'daily-tick', 1)
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


def test_daily_request_counts_pending_after_restart_and_hands_off_once(tmp_path, monkeypatch):
    monkeypatch.setenv('DACHAPPLY_CONTROL_DB', str(tmp_path / 'control.sqlite3'))
    control = processing.store()
    unit = control.enqueue('daily-document', {'args': [1, 2]})
    control.mode('paused')
    assert control.status()['remaining_jobs'] == 1
    control = processing.store()
    control.recover()
    assert control.status()['remaining_jobs'] == 1
    control.mode('running')
    def prepare(*args):
        assert control.status()['running_jobs'] == 1
        processing.handoff_documents()
        child = control.enqueue('documents', document('generated'))
        # No observer can count both the daily request and its admitted variant.
        assert control.status()['remaining_jobs'] == 1
        assert control.status()['running_jobs'] == 0
        assert control.claim(child, 'documents', 1)
        assert control.status()['running_jobs'] == 1
        control.finish(child)
    monkeypatch.setitem(processing._handlers, 'daily-document', prepare)
    processing.execute(control, unit, 'daily-document', [1, 2], {}, 1)  # TASK-358: else the account's lanes, read from the database
    assert control.status()['completed_jobs'] == 1


def test_upgrade_repairs_waiting_daily_request_but_not_finished_wrapper(tmp_path):
    import sqlite3
    path = tmp_path / 'previous.sqlite3'
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE units (id TEXT PRIMARY KEY,kind TEXT,payload TEXT,state TEXT,created REAL,job_key TEXT)')
        db.executemany('INSERT INTO units VALUES (?,?,?,?,?,?)', [
            ('waiting', 'daily-document', json.dumps({'args': [1, 2]}), 'queued', 1, None),
            ('done', 'daily-document', '{}', 'completed', 2, None)])
    control = processing.Store(path)
    assert control.status()['remaining_jobs'] == 1
    assert control.status()['completed_jobs'] == 0


import pytest

@pytest.mark.parametrize('outcome', ['empty', 'failed', 'interrupted'])
def test_scheduled_mailbox_visible_when_check_begins(tmp_path, monkeypatch, settings, outcome):
    from types import SimpleNamespace
    from unittest.mock import Mock
    from jobradar.services import mailbox, followup_digest
    settings.GMAIL_IMAP_USER = 'fixture@example.test'
    settings.GMAIL_IMAP_APP_PASSWORD = 'fixture'
    monkeypatch.setenv('DACHAPPLY_CONTROL_DB', str(tmp_path / 'control.sqlite3'))
    control = processing.store()
    profile = SimpleNamespace(mailbox_check_cadence_minutes=60, mailbox_check_enabled=True,
        mailbox_check_window_start=None, mailbox_check_window_end=None, mailbox_check_calendar_aware=False)
    run = SimpleNamespace(skipped=False, error='', fetched_count=0, save=Mock())
    monkeypatch.setattr(mailbox, 'pending_mailbox_check_request', lambda: None)
    monkeypatch.setattr(mailbox, '_owner_user', lambda: SimpleNamespace(pk=2))
    monkeypatch.setattr(mailbox, 'user_profile_settings', lambda owner: profile)
    monkeypatch.setattr(mailbox, '_claim_run', lambda *args, **kwargs: run)
    monkeypatch.setattr(mailbox, '_release_run', lambda: None)
    monkeypatch.setattr(mailbox, '_alert_on_failure_transition', lambda run: None)
    monkeypatch.setattr(mailbox, 'real_mailbox_messages', lambda: SimpleNamespace(aggregate=lambda *args: {'uid__max': 0}))
    monkeypatch.setattr(followup_digest, 'reconcile_sent_followups', lambda *args: None)
    monkeypatch.setattr(mailbox, 'owned_job_domains', lambda owner: {})
    monkeypatch.setattr(mailbox, 'matched_sender_domains', lambda owner: {})
    monkeypatch.setattr(mailbox, 'owned_jobs', lambda owner: SimpleNamespace(exclude=lambda **kwargs: []))
    seen = []
    class Crash(BaseException):
        pass
    def fetch(last_uid):
        seen.append(control.status()['running_jobs'])
        assert seen[-1] == 1
        if outcome == 'interrupted':
            control.recover()
            assert control.status()['interrupted_jobs'] == 1
            raise Crash()
        if outcome == 'failed':
            raise RuntimeError('fixture fetch failure')
        return []
    monkeypatch.setattr(mailbox, '_default_transport', lambda: SimpleNamespace(fetch_new=fetch))
    if outcome == 'interrupted':
        with pytest.raises(Crash):
            mailbox.check_mailbox_tick()
    else:
        mailbox.check_mailbox_tick()
        state = control.status()
        assert state['failed_jobs'] == (1 if outcome == 'failed' else 0)
        assert state['completed_jobs'] == 0

    assert seen == [1]


def test_pre_key_upgrade_does_not_revive_finished_daily_wrapper(tmp_path):
    import sqlite3
    path = tmp_path / 'original.sqlite3'
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE units (id TEXT PRIMARY KEY,kind TEXT,payload TEXT,state TEXT,created REAL)')
        db.executemany('INSERT INTO units VALUES (?,?,?,?,?)', [
            ('waiting', 'daily-document', json.dumps({'args': [1, 2]}), 'queued', 1),
            ('done', 'daily-document', '{}', 'completed', 2)])
    control = processing.Store(path)
    assert control.status()['remaining_jobs'] == 1
    assert control.status()['completed_jobs'] == 0


def test_daily_analysis_retry_hands_interruption_to_variants(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from jobradar.services import application_prep as prep
    monkeypatch.setenv('DACHAPPLY_CONTROL_DB', str(tmp_path / 'control.sqlite3'))
    control = processing.store()
    for job, owner in ((1, 2), (1, 3), (4, 2)):
        unit = control.enqueue('daily-document', {'args': [job, owner], 'kwargs': {}})
        assert control.claim(unit, 'daily-document', 1)
        control.recover()
    job = SimpleNamespace(id=1, status='reviewed')
    monkeypatch.setattr(prep.JobLead.objects, 'filter', lambda **kwargs: SimpleNamespace(first=lambda: job))
    monkeypatch.setattr(prep, 'is_cv_owner', lambda user: True)
    monkeypatch.setattr(prep.settings, 'CODEX_CV_WORKSPACE', str(tmp_path))
    monkeypatch.setattr(prep, 'public_state', lambda *args, **kwargs: {'variants': []})
    monkeypatch.setattr(prep, 'latest_generated_sources', lambda *args: [])
    monkeypatch.setattr(prep, '_gate', lambda *args: ('', [{'key': 'cv-en', 'document': 'cv', 'language': 'en'}], '', {}))
    monkeypatch.setattr(prep, '_save', lambda *args: None)
    monkeypatch.setattr(prep, '_queue', [])
    monkeypatch.setattr(prep, '_pump', lambda: None)
    prep.prepare(1, SimpleNamespace(pk=2), retry=True)
    assert prep._queue == [(1, 2, 'cv-en')]
    assert control.status()['interrupted_jobs'] == 2


@pytest.mark.parametrize('outcome,remaining', [('empty', 0), ('failed', 1), ('skipped', 1)])
def test_empty_mailbox_retry_resolves_only_successful_matching_check(tmp_path, monkeypatch, outcome, remaining):
    from types import SimpleNamespace
    monkeypatch.setenv('DACHAPPLY_CONTROL_DB', str(tmp_path / 'control.sqlite3'))
    control = processing.store()
    for owner in (2, 3):
        lost = control.enqueue('mailbox-tick', {'args': [], 'kwargs': {'attempt': owner}})
        control.set_job_key(lost, 'mailbox:' + str(owner))
        assert control.claim(lost, 'mailbox-tick', 1)
        control.recover()
    def check():
        if outcome != 'skipped':
            processing.report_mailbox_job(2)
        return SimpleNamespace(fetched_count=0, error='failure' if outcome == 'failed' else '', skipped=outcome == 'skipped'), None
    monkeypatch.setitem(processing._handlers, 'mailbox-tick', check)
    retry = control.enqueue('mailbox-tick', {'args': [], 'kwargs': {}})
    processing.execute(control, retry, 'mailbox-tick', [], {})
    assert control.status()['interrupted_jobs'] == remaining + 1  # other owner's interruption remains
    assert control.status()['completed_jobs'] == 0
