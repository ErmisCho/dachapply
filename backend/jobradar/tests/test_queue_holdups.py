"""TASK-350: a missing salary alone holds nothing, a Ready to submit job is never held, and a re-analysis
that failed transiently retries itself, TRANSIENT_RETRIES times at most, TRANSIENT_DELAY apart.

Hermetic like test_late_text_reanalysis: the fetch and the evaluator's model runner are replaced, no real
timer starts, and the dashboard counts come from a real control Store in tmp_path.
"""
from django.db import OperationalError

import pytest

from jobradar.models import JobEvaluation, JobLead
from jobradar.services import application_prep, processing_control
from jobradar.services.cv_generator import RecoverableGenerationError, _provider_failure
from jobradar.services.posting_fetch import posting_missing
from jobradar.tests.test_application_prep import POSTING, _job, _req, client, generator, owner, workspace  # noqa: F401 -- fixtures
from jobradar.tests.test_application_prep_queue import ACTION, QUEUE, _at, _items, _variant, tasks, timers  # noqa: F401 -- fixtures
from jobradar.tests.test_existing_jobs_pipeline import _limits, _run
from jobradar.tests.test_late_text_reanalysis import _blind, _retry, model  # noqa: F401 -- fixtures
from jobradar.tests.test_link_only_prep import fetch  # noqa: F401 -- fixtures
from jobradar.tests.test_posting_completeness import GERMAN, REASON, _ad

SALARY_HOLD = REASON.format('salary')
START = '2026-11-06T12:00:00+01:00'
LATER = '2099-01-01T00:00:00+00:00'


def _failure():
    return _provider_failure('stream disconnected before completion')  # what a failed CLI run raises


def _hold(job, owner, reason):
    application_prep._save(job, owner.pk, lambda prep: prep.update(reason=reason, variants={}))


def _prep(job, owner):
    return application_prep._state(job, owner)


# --- AC1/AC2: a missing salary is reported, never a hold -----------------------------------------

def test_task350_a_posting_missing_only_the_salary_prepares_and_stays_reported(owner, client, tasks):
    job = _job(owner, 'to_apply', requirements=_req('de'), text=_ad(GERMAN, without=['salary']))
    state = application_prep.prepare(job.id, owner)
    assert state['reason'] == '' and tasks['started'] == [(job.id, 'cv-de')]
    assert posting_missing(job) == ['salary']
    assert client.get(f'/api/jobs/{job.id}/').json()['posting_missing'] == ['salary']


@pytest.mark.parametrize('without, names', [(['tasks'], 'tasks'), (['requirements'], 'requirements'), (['company'], 'company description'),
                                            (['requirements', 'salary'], 'requirements, salary')])
def test_task350_any_other_missing_part_still_holds_as_before(owner, client, tasks, without, names):
    job = _job(owner, 'to_apply', requirements=_req('de'), text=_ad(GERMAN, without=without))
    assert application_prep.prepare(job.id, owner)['reason'] == REASON.format(names) and tasks['started'] == []
    [item] = _items(client)
    assert (item['status'], item['error'], item['incomplete']) == ('blocked', REASON.format(names), True)


def test_task350_a_stored_salary_hold_is_released_and_the_daily_budget_takes_the_job(owner, client, tasks, django_capture_on_commit_callbacks):
    job = _job(owner, 'to_apply', requirements=_req('de'), text=_ad(GERMAN, without=['salary']))
    JobEvaluation.objects.create(job=job, fit_score=70, priority='high', recommendation='apply', summary='')
    _hold(job, owner, SALARY_HOLD)
    assert _items(client) == [] and application_prep.public_state(job, owner)['reason'] == ''
    _limits(owner, prepare=5)
    _run(owner, django_capture_on_commit_callbacks)
    assert tasks['started'] == [(job.id, 'cv-de')]


# --- AC4: Ready to submit ------------------------------------------------------------------------

@pytest.mark.parametrize('reason', [SALARY_HOLD, REASON.format('tasks, salary')])
def test_task350_a_ready_to_submit_job_never_shows_a_stored_hold(owner, client, tasks, reason):
    job = _job(owner, 'ready_to_submit', requirements=_req('de'), text=_ad(GERMAN, without=['tasks', 'salary']))
    _hold(job, owner, reason)
    assert _items(client) == [] and application_prep.public_state(job, owner)['reason'] == ''


def test_task350_a_retry_in_ready_to_submit_is_not_held_again(owner, client, tasks):
    job = _job(owner, 'ready_to_submit', requirements=_req('de'), text=_ad(GERMAN, without=['tasks']))
    state = application_prep.prepare(job.id, owner, retry=True)
    assert state['reason'] == '' and tasks['started'] == [(job.id, 'cv-de')]
    assert [item['status'] for item in _items(client)] == ['running']


# --- AC3: a transient re-analysis failure retries itself -----------------------------------------

def test_task350_a_transient_failure_retries_after_the_delay_and_prepares(owner, client, tasks, fetch, model, timers, monkeypatch, django_capture_on_commit_callbacks):
    _at(monkeypatch, START)
    job = _blind(owner, model)
    model['answers'] = [_failure(), 'maybe']
    _retry(client, job, django_capture_on_commit_callbacks)
    [item] = _items(client)
    assert item['error'] == 'Re-analysis failed: The selected model could not complete the request. Press Retry.'
    assert item['retry_at'] == '2026-11-06T12:10:00+01:00' and timers[-1].interval == 600
    _at(monkeypatch, '2026-11-06T12:09:59+01:00')
    assert application_prep.retry_due() == 0 and len(model['calls']) == 1
    _at(monkeypatch, '2026-11-06T12:10:00+01:00')
    with django_capture_on_commit_callbacks(execute=True):
        assert application_prep.retry_due() == 1
    assert len(model['calls']) == 2 and tasks['started'] == [(job.id, 'cv-de')]
    assert 'auto_retries' not in _prep(job, owner)  # the run that worked ended this failure's count


def test_task350_a_pool_timeout_counts_as_transient(owner, client, tasks, fetch, model, timers, monkeypatch, django_capture_on_commit_callbacks):
    _at(monkeypatch, START)
    job = _blind(owner, model)
    model['answers'] = [OperationalError("couldn't get a connection after 30.00 sec")]
    _retry(client, job, django_capture_on_commit_callbacks)
    assert _prep(job, owner)['retry_at'] == '2026-11-06T12:10:00+01:00'


def test_task350_the_cap_holds_and_survives_a_restart(owner, client, tasks, fetch, model, timers, monkeypatch, django_capture_on_commit_callbacks):
    _at(monkeypatch, START)
    job = _blind(owner, model)
    model['answers'] = [_failure() for _ in range(9)]
    _retry(client, job, django_capture_on_commit_callbacks)
    for run in (2, 3):
        _at(monkeypatch, f'209{run}-01-01T00:00:00+00:00')
        with django_capture_on_commit_callbacks(execute=True):
            assert application_prep.retry_due() == 1
        assert len(model['calls']) == run
    [item] = _items(client)  # failed for good, and still visible with its Retry
    assert (item['status'], item['retry_at']) == ('blocked', None) and item['error'].startswith(application_prep.REANALYSIS_FAILED)
    prep = _prep(job, owner)
    assert prep['auto_retries'] == application_prep.TRANSIENT_RETRIES == 2 and prep['retry_at'] is None
    # A restart starts from the sidecar with nothing in memory, and neither it nor the clock runs anything more.
    monkeypatch.setattr(application_prep, '_timer', None)
    with django_capture_on_commit_callbacks(execute=True):
        application_prep.resume_queue()
    _at(monkeypatch, LATER)
    assert application_prep.retry_due() == 0 and len(model['calls']) == 3 and application_prep._timer is None


def test_task350_a_restart_runs_a_recorded_retry_once_and_keeps_its_count(owner, client, tasks, fetch, model, timers, monkeypatch, django_capture_on_commit_callbacks):
    _at(monkeypatch, START)
    job = _blind(owner, model)
    model['answers'] = [_failure(), _failure(), _failure()]
    _retry(client, job, django_capture_on_commit_callbacks)
    _at(monkeypatch, LATER)
    monkeypatch.setattr(application_prep, '_timer', None)
    with django_capture_on_commit_callbacks(execute=True):
        application_prep.resume_queue()
    assert len(model['calls']) == 2 and _prep(job, owner)['auto_retries'] == 1


@pytest.mark.parametrize('error', [RecoverableGenerationError('The selected model returned an invalid response.', 'not JSON'),
                                   RuntimeError('The codex CLI must be installed on the generation server.'),
                                   ValueError('a defect')], ids=['bad-answer', 'bad-setup', 'defect'])
def test_task350_a_failure_that_would_fail_again_is_not_retried(owner, client, tasks, fetch, model, timers, monkeypatch, django_capture_on_commit_callbacks, error):
    _at(monkeypatch, START)
    job = _blind(owner, model)
    model['answers'] = [error]
    _retry(client, job, django_capture_on_commit_callbacks)
    assert _prep(job, owner)['retry_at'] is None and timers == []
    _at(monkeypatch, LATER)
    assert application_prep.retry_due() == 0 and len(model['calls']) == 1


def test_task350_a_first_analysis_failure_is_not_retried(owner, tasks, fetch, model, timers):
    job = JobLead.objects.create(company='ACME', title='Python Engineer', status='new', created_by=owner, url='https://jobs.example.test/first', original_source_text=POSTING)
    model.update(job_id=job.id, answers=[_failure()])
    assert application_prep.start_pipeline(job.id, owner, force=True)
    prep = _prep(job, owner)
    assert prep['reason'].startswith('Analysis failed') and prep['retry_at'] is None and timers == []


def test_task350_a_reanalysis_beside_documents_retries_with_its_own_note(owner, tasks, fetch, model, timers, monkeypatch, django_capture_on_commit_callbacks):
    """queue_action's retry cannot reach a job with variants, and the note must stay: only CHANGED redoes
    documents when the outcome is the same, so a stale re-check must not turn into a paid redo."""
    _at(monkeypatch, START)
    job = _job(owner, 'to_apply', requirements=_req('de'), text=POSTING)
    JobEvaluation.objects.create(job=job, fit_score=70, priority='high', recommendation='maybe', summary='')
    application_prep._save(job, owner.pk, lambda prep: prep.update(variants={'cv-de': {'document': 'cv', 'language': 'de', 'status': 'ready', 'task_id': '', 'error': '', 'files': {}}}))
    model.update(job_id=job.id, answers=[_failure(), 'maybe'])
    assert application_prep.start_pipeline(job.id, owner, force=True, reanalyse=application_prep.REANALYSED)
    assert _prep(job, owner)['pipeline']['note'] == application_prep.REANALYSED
    _at(monkeypatch, '2026-11-06T12:10:00+01:00')
    with django_capture_on_commit_callbacks(execute=True):
        assert application_prep.retry_due() == 1
    assert len(model['calls']) == 2 and tasks['started'] == [] and _variant(job, owner, 'cv-de')['status'] == 'ready'


def test_task350_pause_spends_nothing_and_resume_runs_the_retry(owner, client, tasks, fetch, model, timers, monkeypatch, tmp_path, django_capture_on_commit_callbacks):
    _at(monkeypatch, START)
    job = _blind(owner, model)
    model['answers'] = [_failure(), 'maybe']
    _retry(client, job, django_capture_on_commit_callbacks)
    monkeypatch.setenv('DACHAPPLY_CONTROL_DB', str(tmp_path / 'control.sqlite3'))
    processing_control.store().mode('paused')
    _at(monkeypatch, '2026-11-06T12:10:00+01:00')
    assert application_prep.retry_due() == 0 and len(model['calls']) == 1
    prep = _prep(job, owner)
    assert prep['retry_at'] == '2026-11-06T12:10:00+01:00' and 'auto_retries' not in prep
    assert timers[-1].interval == 60 and not timers[-1].cancelled  # it looks again; Resume calls nothing here
    monkeypatch.delenv('DACHAPPLY_CONTROL_DB')  # resumed; the worker then runs in-thread as in every test here
    with django_capture_on_commit_callbacks(execute=True):
        assert application_prep.retry_due() == 1
    assert len(model['calls']) == 2


def test_task350_a_failed_retry_scan_arms_the_timer_again(owner, timers, monkeypatch):
    def outage():
        raise OperationalError("couldn't get a connection after 30.00 sec")
    monkeypatch.setattr(application_prep, 'retry_due', outage)
    application_prep._retry_worker()
    assert timers[-1].interval <= 60 and not timers[-1].cancelled


# --- Honest counts: the Queue summary and the dashboard ------------------------------------------

@pytest.mark.parametrize('last, failed, completed', [(_failure, 1, 0), (lambda: 'maybe', 0, 1)], ids=['gave-up', 'recovered'])
def test_task350_retried_attempts_count_as_one_job(owner, client, tasks, fetch, model, timers, monkeypatch, tmp_path, django_capture_on_commit_callbacks, last, failed, completed):
    _at(monkeypatch, START)
    control = processing_control.Store(tmp_path / 'control.sqlite3')
    job = _blind(owner, model)
    model['answers'] = [_failure(), _failure(), last()]

    def attempt(job_id, user, force=False, reanalyse=''):  # start_pipeline's durable unit, run here on a real store
        args = [job_id, user.pk, reanalyse]
        processing_control.execute(control, control.enqueue('pipeline', {'args': args, 'kwargs': {}}), 'pipeline', args, {})
    monkeypatch.setattr(application_prep, 'start_pipeline', attempt)
    attempt(job.id, owner, reanalyse=application_prep.CHANGED)
    summary = client.get(QUEUE).json()['summary']
    assert (summary['analyses_left'], summary['documents_left'], summary['total']) == (0, 0, 0)  # waiting, not running
    assert [item['status'] for item in _items(client)] == ['blocked']
    for year in (2097, 2098):
        _at(monkeypatch, f'{year}-01-01T00:00:00+00:00')
        with django_capture_on_commit_callbacks(execute=True):
            assert application_prep.retry_due() == 1
    status = control.status()
    assert len(model['calls']) == 3 and (status['failed_jobs'], status['completed_jobs'], status['remaining_jobs']) == (failed, completed, 0)
