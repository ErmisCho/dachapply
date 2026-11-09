"""TASK-361: a job the owner dropped (Skipped, Archived) or the app recommends skipping leaves the Blocked list and
spends no automatic model run, whatever blocked it. The row is hidden, not destroyed, and comes back with a new
verdict. A job the owner moved forward (To apply, Ready to submit) despite the skip stays, because they chose it.

Hermetic like test_existing_jobs_pipeline: the fetch and the evaluator's model runner are replaced, no real timer
starts, and the workers run in-thread.
"""
import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from jobradar.models import ApplicationNote, JobEvaluation, JobLead
from jobradar.services import application_prep
from jobradar.tests.test_application_prep import client, generator, owner, workspace  # noqa: F401 -- fixtures
from jobradar.tests.test_application_prep_queue import QUEUE, _evaluate, _items, tasks, timers  # noqa: F401 -- fixtures
from jobradar.tests.test_auto_pipeline import model  # noqa: F401 -- fixture
from jobradar.tests.test_existing_jobs_pipeline import CHANGED_AD, _analysed, _evaluated, _limits, _prepared, _refresh, _run, today  # noqa: F401 -- fixture
from jobradar.tests.test_link_only_prep import FAILED, REFUSED, SUBSTANTIAL, _link_only, fetch  # noqa: F401 -- fixtures

FAILED_ANALYSIS = f'{application_prep.REANALYSIS_FAILED}: The selected model could not complete the request. Press Retry.'
PAST = '2026-01-01T00:00:00+00:00'


def _block(job, owner, reason=FAILED_ANALYSIS, retry_at=None):
    application_prep._save(job, owner.pk, lambda prep: prep.update(
        reason=reason, retry_at=retry_at, pipeline={'stage': 'failed', 'at': PAST, 'error': 'x', 'note': application_prep.REANALYSED}))
    return job


def _blocked_ids(client):
    return [item['job_id'] for item in _items(client) if item['status'] == 'blocked']


# --- AC1: the list ----------------------------------------------------------------------------------

@pytest.mark.parametrize('status', ['new', 'reviewed'])
@pytest.mark.parametrize('reason', [FAILED_ANALYSIS, REFUSED, application_prep.PIPELINE_INTERRUPTED, application_prep.DAILY_LIMIT.format(3),
                                    f'{application_prep.INCOMPLETE}: missing tasks.', 'Analysis failed: no model. Press Retry.'])
def test_a_job_recommended_skip_leaves_the_blocked_list_whatever_blocked_it(owner, client, reason, status):
    hidden = _block(_evaluated(owner, 'skip', recommendation='skip', status=status), owner, reason)
    shown = _block(_evaluated(owner, 'apply', status=status), owner, reason)
    assert hidden.id not in _blocked_ids(client) and _blocked_ids(client) == [shown.id]


@pytest.mark.parametrize('status', ['skipped', 'archived'])
def test_a_skipped_or_archived_job_stays_off_the_list_with_or_without_a_skip_verdict(owner, client, status):
    _block(_evaluated(owner, 'apply', status=status), owner)
    _block(_evaluated(owner, 'skip', recommendation='skip', status=status), owner)
    assert _blocked_ids(client) == []


def test_only_the_latest_evaluation_counts(owner, client):
    job = _block(_evaluated(owner, 'changed-its-mind', recommendation='skip', days=2), owner)
    JobEvaluation.objects.create(job=job, fit_score=70, priority='high', recommendation='maybe', summary='')
    assert _blocked_ids(client) == [job.id]


@pytest.mark.parametrize('status', ['to_apply', 'ready_to_submit'])
def test_a_job_the_owner_moved_forward_stays_listed_despite_a_skip(owner, client, status):
    job = _block(_evaluated(owner, 'chosen', recommendation='skip', status=status), owner)
    assert _blocked_ids(client) == [job.id]


# --- AC2: no automatic run --------------------------------------------------------------------------

def test_a_due_retry_of_a_skip_job_spends_nothing_and_stays_recorded(owner, client, tasks, fetch, model, timers, today, django_capture_on_commit_callbacks):
    job = _block(_evaluated(owner, 'skip', recommendation='skip'), owner, retry_at=PAST)
    with django_capture_on_commit_callbacks(execute=True):
        assert application_prep.retry_due() == 0
    prep = application_prep._state(job, owner)
    assert model['calls'] == [] and prep['retry_at'] == PAST and 'auto_retries' not in prep


def test_a_later_retry_of_a_skip_job_arms_no_timer(owner, tasks, fetch, model, timers):
    _block(_evaluated(owner, 'skip', recommendation='skip'), owner, retry_at='2099-01-01T00:00:00+00:00')
    assert application_prep.retry_due() == 0 and application_prep._timer is None


def test_a_due_document_retry_of_a_skip_job_spends_nothing(owner, tasks, fetch, model, timers, today, workspace):
    job = _evaluated(owner, 'skip', recommendation='skip')
    application_prep._save(job, owner.pk, lambda prep: prep.update(variants={'cv-de': {'document': 'cv', 'language': 'de', 'status': 'failed', 'retry_at': PAST}}))
    assert application_prep.retry_due() == 0 and tasks['started'] == []
    assert application_prep._state(job, owner)['variants']['cv-de']['status'] == 'failed'


@pytest.mark.parametrize('status', ['to_apply', 'ready_to_submit'])
def test_the_due_retry_of_a_job_the_owner_moved_forward_still_runs(owner, tasks, fetch, model, timers, today, django_capture_on_commit_callbacks, status):
    job = _block(_evaluated(owner, 'chosen', recommendation='skip', status=status), owner, retry_at=PAST)
    model['answers'] = ['skip']
    with django_capture_on_commit_callbacks(execute=True):
        assert application_prep.retry_due() == 1
    assert _analysed(model) == [job.id]


def test_the_daily_run_leaves_a_skip_job_alone_and_keeps_the_budget(owner, tasks, fetch, model, today, workspace, django_capture_on_commit_callbacks):
    _limits(owner, analyse=1, prepare=None, days=7)
    _block(_evaluated(owner, 'stale', recommendation='skip', days=30), owner)
    waiting = _evaluated(owner, 'stale-changed', recommendation='skip', days=30)
    application_prep._save(waiting, owner.pk, lambda prep: prep.update(posting_changed=True))
    redo, _ = _prepared(owner, workspace, {'cv-de': ('ready', None)}, n='redo', recommendation='skip')
    JobLead.objects.filter(pk=redo.pk).update(status='reviewed')
    application_prep._save(redo, owner.pk, lambda prep: prep.update(redo_pending=True))
    wanted = _evaluated(owner, 'wanted', days=30)
    model['answers'] = ['apply']
    _run(owner, django_capture_on_commit_callbacks)
    assert _analysed(model) == [wanted.id] and all(job_id == wanted.id for job_id, _ in tasks['started'])
    assert application_prep._state(waiting, owner)['posting_changed'] is True


def test_the_daily_run_still_reanalyses_a_stale_job_the_owner_moved_forward(owner, tasks, fetch, model, today, django_capture_on_commit_callbacks):
    _limits(owner, analyse=1, days=7)
    job = _evaluated(owner, 'chosen', recommendation='skip', days=30, status='to_apply')
    model['answers'] = ['skip']
    _run(owner, django_capture_on_commit_callbacks)
    assert _analysed(model) == [job.id]


def test_the_automatic_refresh_takes_the_text_of_a_skip_job_without_a_model_run(owner, client, tasks, fetch, model, today, django_capture_on_commit_callbacks):
    _limits(owner, analyse=None)
    job = _evaluated(owner, 'skip', recommendation='skip', text=SUBSTANTIAL)
    fetch['result'] = {'ok': True, 'text': CHANGED_AD, 'error': '', 'final_url': ''}
    _refresh(client, django_capture_on_commit_callbacks)
    job.refresh_from_db()
    assert job.original_source_text == CHANGED_AD and model['calls'] == []
    assert 'posting_changed' not in application_prep._state(job, owner)


def test_the_owners_use_fetched_still_reanalyses_a_skip_job(owner, client, tasks, fetch, model, today, django_capture_on_commit_callbacks):
    _limits(owner, analyse=None)
    job = _evaluated(owner, 'skip', recommendation='skip', text=SUBSTANTIAL)
    model['answers'] = ['maybe']
    with django_capture_on_commit_callbacks(execute=True):
        assert client.patch(f'/api/jobs/{job.id}/source-text/', {'original_source_text': CHANGED_AD}, format='json').status_code == 200
    assert _analysed(model) == [job.id]


# --- AC3: a new verdict brings it back --------------------------------------------------------------

@pytest.mark.parametrize('recommendation', ['apply', 'maybe'])
def test_a_new_verdict_brings_the_blocked_reason_and_its_retry_back(owner, client, tasks, fetch, model, timers, today, django_capture_on_commit_callbacks, recommendation):
    job = _block(_evaluated(owner, 'skip', recommendation='skip'), owner, retry_at=PAST)
    assert _blocked_ids(client) == [] and application_prep.retry_due() == 0
    JobEvaluation.objects.create(job=job, fit_score=70, priority='high', recommendation=recommendation, summary='')
    [item] = _items(client)
    assert (item['job_id'], item['status'], item['error']) == (job.id, 'blocked', FAILED_ANALYSIS)
    model['answers'] = ['maybe']
    with django_capture_on_commit_callbacks(execute=True):
        assert application_prep.retry_due() == 1
    assert _analysed(model) == [job.id]


def test_a_new_analysis_through_the_import_shows_the_jobs_real_block(owner, client, tasks, fetch, django_capture_on_commit_callbacks):
    fetch['result'] = FAILED
    job = _link_only(owner)
    JobEvaluation.objects.create(job=job, fit_score=0, priority='low', recommendation='skip', summary='')
    _block(job, owner, REFUSED)
    assert _blocked_ids(client) == []
    _evaluate(job, owner, 'apply', django_capture_on_commit_callbacks)
    [item] = _items(client)
    assert (item['job_id'], item['status'], item['error']) == (job.id, 'blocked', REFUSED)


# --- AC4: hidden, not destroyed, and the counts stay honest ------------------------------------------

def test_hiding_destroys_nothing_and_changes_no_summary(owner, client, workspace):
    kept = _block(_evaluated(owner, 'kept'), owner)
    before = client.get(QUEUE).json()['summary']
    job = _block(_evaluated(owner, 'skip', recommendation='skip'), owner, retry_at=PAST)
    ApplicationNote.objects.create(job=job, note='keep me')
    prep = application_prep._state(job, owner)
    data = client.get(QUEUE).json()
    assert data['summary'] == before and [item['job_id'] for item in data['items']] == [kept.id]
    assert JobLead.objects.filter(pk=job.pk, status='new').exists() and job.notes.count() == 1
    assert job.evaluations.count() == 1 and application_prep._state(job, owner) == prep


def test_a_listed_failed_document_of_a_skip_job_promises_no_retry(owner, client, workspace):
    job = _evaluated(owner, 'skip', recommendation='skip')
    application_prep._save(job, owner.pk, lambda prep: prep.update(variants={'cv-de': {'document': 'cv', 'language': 'de', 'status': 'failed', 'retry_at': PAST}}))
    [item] = _items(client)
    assert (item['status'], item['retry_at']) == ('failed', None)


def _poll_queries(client):
    """The endpoint's own queries: the request-usage middleware's writes are not the queue's."""
    with CaptureQueriesContext(connection) as captured:
        assert client.get(QUEUE).status_code == 200
    return [query['sql'] for query in captured if 'sitevisitor' not in query['sql'] and 'usage' not in query['sql'] and 'SAVEPOINT' not in query['sql']]


def test_the_queue_poll_stays_at_two_queries_with_no_query_per_job(owner, client, workspace):
    for n in range(2):
        _block(_evaluated(owner, f'few-{n}', recommendation='skip'), owner)
    few = _poll_queries(client)
    for n in range(8):
        _block(_evaluated(owner, f'many-{n}', recommendation='skip' if n % 2 else 'apply'), owner)
    assert len(_poll_queries(client)) == len(few) == 2  # measured 2 before TASK-361
