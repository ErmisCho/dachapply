"""TASK-324/325: adding a job with a link fetches, analyses and (apply/maybe) prepares its documents on its
own, and the Queue shows each pipeline step.

Hermetic like test_late_text_reanalysis: the fetch and the evaluator's model runner are replaced, and the
pipeline worker runs in-thread (the generator fixture's SyncThread), inside this test's transaction.
"""
from datetime import datetime

import pytest

from jobradar.models import JobEvaluation, JobLead, UserProfile
from jobradar.services import application_prep, job_evaluator
from jobradar.services.cv_generator import RecoverableGenerationError
from jobradar.tests.test_application_prep import POSTING, _req, client, generator, owner, workspace  # noqa: F401 -- fixtures
from jobradar.tests.test_application_prep_queue import ACTION, _at, _items, tasks, timers  # noqa: F401 -- fixtures
from jobradar.tests.test_job_evaluator import OLLAMA_OPTION, evaluation_for
from jobradar.tests.test_link_only_prep import LINK, _blocked, fetch  # noqa: F401 -- fixtures

INCOMPLETE_POSTING = 'We are hiring a Python engineer. Your tasks: build APIs with Django and Postgres every day. ' * 3


@pytest.fixture
def model(monkeypatch):
    """state['answers'] is popped per evaluation -- a recommendation, or an exception; calls records (job_ids, commit)."""
    monkeypatch.setattr(application_prep, '_piping', set())
    state = {'answers': [], 'calls': []}
    real = job_evaluator.evaluate_jobs

    def evaluate(job_ids, user, *args, commit=False, **kwargs):
        state['calls'].append((list(job_ids), commit))
        state['job_id'] = job_ids[0]
        return real(job_ids, user, *args, commit=commit, **kwargs)

    def run(prompt, schema, *args, **kwargs):
        answer = state['answers'].pop(0)
        if isinstance(answer, Exception):
            raise answer
        job = JobLead.objects.get(pk=state['job_id'])
        return {'evaluations': [evaluation_for(job, recommendation=answer, fit_score=44 if answer == 'skip' else 70)]}
    monkeypatch.setattr(job_evaluator, 'evaluate_jobs', evaluate)
    monkeypatch.setattr(job_evaluator, 'validate_model_capability', lambda *a, **k: OLLAMA_OPTION)
    monkeypatch.setattr(job_evaluator, 'run_structured_model', run)
    # The apply/maybe hook's requirements analysis (TASK-308) answers German, one CV.
    monkeypatch.setattr(application_prep, 'run_structured_model', lambda *a, **k: {'application_requirements': _req('de')})
    return state


def _add(client, capture, url=LINK):
    with capture(execute=True):
        response = client.post('/api/jobs/', {'url': url, 'company': 'ACME', 'title': 'Python Engineer'}, format='json')
    assert response.status_code == 201, response.content
    return JobLead.objects.get(pk=response.data['id'])


def _pipeline(job, owner):
    return application_prep._state(job, owner).get('pipeline')


def _retry(client, job, capture):
    with capture(execute=True):
        assert client.post(ACTION, {'job_id': job.id, 'key': '', 'action': 'retry'}, format='json').status_code == 200


def test_single_add_fetches_analyses_commits_and_an_apply_queues_documents(owner, client, tasks, fetch, model, django_capture_on_commit_callbacks):
    model['answers'] = ['apply']
    job = _add(client, django_capture_on_commit_callbacks)
    assert fetch['calls'] == [LINK] and model['calls'] == [([job.id], True)]
    assert JobEvaluation.objects.get(job=job).recommendation == 'apply'
    # The documents follow through the TASK-312 hook, and their rows replace the pipeline's.
    assert tasks['started'] == [(job.id, 'cv-de')] and _pipeline(job, owner)['stage'] == 'analysed'
    assert [(item['key'], item['status']) for item in _items(client)] == [('cv-de', 'running')]


def test_an_analysed_job_stays_listed_while_its_requirements_are_analysed(owner, client, tasks, fetch, model, monkeypatch):
    job = JobLead.objects.create(company='ACME', title='Python Engineer', created_by=owner, url=LINK, original_source_text=POSTING)
    application_prep._save(job, owner.pk, lambda prep: prep.update(pipeline={'stage': 'analysed', 'at': 'T'}, reason=application_prep.ANALYSING, variants={}))
    monkeypatch.setattr(application_prep, '_analysing', {job.id})  # TASK-340: listed while the analysis thread runs
    [row] = _items(client)
    assert (row['key'], row['status'], row['label'], row['document']) == ('', 'running', 'Analysing requirements', None)
    application_prep._save(job, owner.pk, lambda prep: prep.update(reason=''))  # analysed and done: nothing left to show
    application_prep._analysing.discard(job.id)
    assert _items(client) == []


def test_bulk_add_runs_each_link_one_after_the_other(owner, client, tasks, fetch, model, django_capture_on_commit_callbacks):
    model['answers'] = ['skip', 'skip']
    with django_capture_on_commit_callbacks(execute=True):
        response = client.post('/api/jobs/bulk-create/', {'raw_description': 'https://jobs.example.test/a\nhttps://jobs.example.test/b'}, format='json')
    assert response.status_code == 201, response.content
    ids = [row['id'] for row in response.data['created']]
    assert model['calls'] == [([ids[0]], True), ([ids[1]], True)] and not application_prep._pipeline_lock.locked()


def test_a_skip_queues_nothing_and_shows_as_done_with_its_score(owner, client, tasks, fetch, model, django_capture_on_commit_callbacks):
    model['answers'] = ['skip']
    job = _add(client, django_capture_on_commit_callbacks)
    assert tasks['started'] == [] and _pipeline(job, owner)['stage'] == 'skipped' and _pipeline(job, owner)['fit_score'] == 44
    [row] = _items(client)
    assert (row['key'], row['status'], row['label'], row['error'], row['document']) == ('', 'skipped', 'Not applying', 'Skip · fit 44', None)
    assert row['finished_at'] == _pipeline(job, owner)['at']


def test_a_job_with_an_evaluation_or_no_link_or_a_non_owner_runs_nothing(owner, client, tasks, fetch, model, django_capture_on_commit_callbacks):
    job = JobLead.objects.create(company='ACME', title='Python Engineer', created_by=owner, url=LINK, original_source_text=POSTING)
    JobEvaluation.objects.create(job=job, fit_score=50, priority='low', recommendation='maybe', summary='')
    assert application_prep.start_pipeline(job.id, owner) is False
    with django_capture_on_commit_callbacks(execute=True):
        assert client.post('/api/jobs/', {'company': 'NoLink', 'title': 'Engineer', 'original_source_text': POSTING}, format='json').status_code == 201
    UserProfile.objects.filter(user=owner).update(can_generate_cv=False)
    owner.refresh_from_db()
    _add(client, django_capture_on_commit_callbacks, url='https://jobs.example.test/other')
    assert model['calls'] == []


def test_a_public_submission_does_not_run(owner, client, tasks, fetch, model, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        response = client.post('/api/public/submit/', {'company': 'Friend', 'title': 'Engineer', 'url': LINK}, format='json')
    assert response.status_code == 201, response.content
    assert model['calls'] == [] and fetch['calls'] == []


def test_an_incomplete_posting_is_analysed_then_held_as_today(owner, client, tasks, fetch, model, django_capture_on_commit_callbacks):
    fetch['result'] = {'ok': True, 'text': INCOMPLETE_POSTING, 'error': '', 'final_url': LINK}
    model['answers'] = ['maybe']
    job = _add(client, django_capture_on_commit_callbacks)
    assert model['calls'] == [([job.id], True)] and tasks['started'] == []
    [row] = _items(client)
    assert row['status'] == 'blocked' and row['incomplete'] and row['error'].startswith(application_prep.INCOMPLETE)


def test_the_daily_limit_holds_later_adds_and_retry_runs_one_now(owner, client, tasks, fetch, model, django_capture_on_commit_callbacks):
    UserProfile.objects.filter(user=owner).update(auto_pipeline_daily_limit=1)
    model['answers'] = ['skip', 'skip']
    _add(client, django_capture_on_commit_callbacks)
    held = _add(client, django_capture_on_commit_callbacks, url='https://jobs.example.test/second')
    assert len(model['calls']) == 1 and _pipeline(held, owner)['stage'] == 'limit'
    reason = 'Daily limit of 1 automatic runs reached. Press Retry to run it now, or raise the limit on the Profile page.'
    assert {**_blocked(held, reason), 'job_status': 'new'} in _items(client)
    _retry(client, held, django_capture_on_commit_callbacks)
    assert model['calls'][-1] == ([held.id], True) and _pipeline(held, owner)['stage'] == 'skipped'


def test_a_limit_of_zero_runs_nothing(owner, client, tasks, fetch, model, django_capture_on_commit_callbacks):
    UserProfile.objects.filter(user=owner).update(auto_pipeline_daily_limit=0)
    job = _add(client, django_capture_on_commit_callbacks)
    assert model['calls'] == [] and fetch['calls'] == [] and _pipeline(job, owner) is None and _items(client) == []


def test_a_failure_blocks_with_retry_and_a_usage_limit_retries_after_the_reset(owner, client, tasks, fetch, model, timers, monkeypatch, django_capture_on_commit_callbacks):
    _at(monkeypatch, '2026-10-21T17:00:00+02:00')
    model['answers'] = [RecoverableGenerationError('Usage limit reached; resets at 18:51.', usage_limit=True,
                                                   reset_at=datetime.fromisoformat('2026-10-21T18:51:00+02:00')), 'maybe']
    job = _add(client, django_capture_on_commit_callbacks)
    assert _pipeline(job, owner)['stage'] == 'failed' and not JobEvaluation.objects.filter(job=job).exists()
    blocked = {**_blocked(job, 'Analysis failed: Usage limit reached; resets at 18:51. Press Retry.'), 'job_status': 'new', 'retry_at': '2026-10-21T18:52:00+02:00'}
    assert _items(client) == [blocked]
    _at(monkeypatch, '2026-10-21T18:52:00+02:00')
    with django_capture_on_commit_callbacks(execute=True):
        assert application_prep.retry_due() == 1
    assert model['calls'] == [([job.id], True)] * 2 and tasks['started'] == [(job.id, 'cv-de')]


def test_a_plain_failure_is_not_retried_automatically_but_retry_reruns_it(owner, client, tasks, fetch, model, django_capture_on_commit_callbacks):
    model['answers'] = [RuntimeError('provider down'), 'skip']
    job = _add(client, django_capture_on_commit_callbacks)
    prep = application_prep._state(job, owner)
    assert prep['reason'] == 'Analysis failed: provider down. Press Retry.' and prep['retry_at'] is None
    _retry(client, job, django_capture_on_commit_callbacks)
    assert len(model['calls']) == 2 and _pipeline(job, owner)['stage'] == 'skipped'


def test_running_stages_show_under_running_and_a_restart_marks_them_failed(owner, client, tasks, fetch, model, django_capture_on_commit_callbacks):
    UserProfile.objects.filter(user=owner).update(auto_pipeline_daily_limit=0)  # added, never run: the stages are set by hand
    model['answers'] = ['skip']
    job = _add(client, django_capture_on_commit_callbacks)
    for stage, label in application_prep.PIPELINE_RUNNING.items():
        application_prep._save(job, owner.pk, lambda prep, stage=stage: prep.update(pipeline={'stage': stage, 'at': '2026-10-21T08:00:00+00:00'}))
        [row] = _items(client)
        assert (row['status'], row['label'], row['document'], row['started_at']) == ('running', label, None, '2026-10-21T08:00:00+00:00')
    application_prep.resume_queue()  # nothing is in _piping: the restart stopped it
    assert _items(client) == [{**_blocked(job, application_prep.PIPELINE_INTERRUPTED), 'job_status': 'new'}]
    _retry(client, job, django_capture_on_commit_callbacks)  # Retry runs it, past the limit
    assert model['calls'] == [([job.id], True)] and _pipeline(job, owner)['stage'] == 'skipped'


def test_no_pipeline_row_once_variants_exist(owner, client, tasks, fetch, model, django_capture_on_commit_callbacks):
    model['answers'] = ['apply']
    job = _add(client, django_capture_on_commit_callbacks)
    application_prep._save(job, owner.pk, lambda prep: prep.update(pipeline={'stage': 'analysing', 'at': '2026-10-21T08:00:00+00:00'}))
    assert [item['key'] for item in _items(client)] == ['cv-de']


def test_profile_round_trip_of_the_daily_limit(owner, client):
    assert client.get('/api/profile/').data['auto_pipeline_daily_limit'] == 50
    assert client.patch('/api/profile/', {'auto_pipeline_daily_limit': 0}, format='json').data['auto_pipeline_daily_limit'] == 0
    assert UserProfile.objects.get(user=owner).auto_pipeline_daily_limit == 0
    assert client.get('/api/profile/').data['auto_pipeline_daily_limit'] == 0
    assert client.patch('/api/profile/', {'auto_pipeline_daily_limit': -1}, format='json').status_code == 400
    assert client.patch('/api/profile/', {'auto_pipeline_daily_limit': 'many'}, format='json').status_code == 400
    assert UserProfile.objects.get(user=owner).auto_pipeline_daily_limit == 0
