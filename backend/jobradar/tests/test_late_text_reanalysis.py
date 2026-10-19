"""TASK-319: a job analysed from its link alone is analysed again once its posting is fetched (Queue
Retry, the job page's fetch, the automatic refresh) before documents are prepared from that blind verdict.

Hermetic like test_link_only_prep: the fetch and the evaluator's model runner are replaced, and the
re-analysis worker runs in-thread (the generator fixture's SyncThread), inside this test's transaction.
"""
from datetime import datetime
from unittest.mock import patch

import pytest

from jobradar.models import JobEvaluation, JobLead
from jobradar.services import application_prep
from jobradar.services.cv_generator import RecoverableGenerationError
from jobradar.tests.test_application_prep import POSTING, _req, client, generator, owner, workspace  # noqa: F401 -- fixtures
from jobradar.tests.test_application_prep_queue import ACTION, _at, _items, tasks, timers  # noqa: F401 -- fixtures
from jobradar.tests.test_job_evaluator import OLLAMA_OPTION, evaluation_for
from jobradar.tests.test_link_only_prep import LINK, THIN, _blocked, _link_only, fetch  # noqa: F401 -- fixtures


@pytest.fixture
def model(monkeypatch):
    """The evaluator's model: state['answers'] is popped per run -- a recommendation, or an exception."""
    monkeypatch.setattr(application_prep, '_reanalysing', set())
    state = {'answers': [], 'calls': []}

    def run(prompt, schema, provider, model, effort, speed, **kwargs):
        state['calls'].append({'prompt': prompt, 'choice': (provider, model, effort, speed)})
        answer = state['answers'].pop(0)
        if isinstance(answer, Exception):
            raise answer
        job = JobLead.objects.get(pk=state['job_id'])
        return {'evaluations': [evaluation_for(job, recommendation=answer, fit_score=44 if answer == 'skip' else 70)]}
    with patch('jobradar.services.job_evaluator.validate_model_capability', return_value=OLLAMA_OPTION), \
         patch('jobradar.services.job_evaluator.run_structured_model', side_effect=run):
        yield state


def _blind(owner, model, status='to_apply', text=LINK):
    """ÖBB job 1845: evaluated 'maybe' (fit 0) from its link alone, then blocked for want of a posting."""
    job = _link_only(owner, status, text=text)
    JobEvaluation.objects.create(job=job, fit_score=0, priority='low', recommendation='maybe', summary='Analysed from the link only.')
    model['job_id'] = job.id
    if text == LINK:
        application_prep.prepare(job.id, owner)  # 'The job has no usable posting text yet.'
    return job


def _retry(client, job, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        assert client.post(ACTION, {'job_id': job.id, 'key': '', 'action': 'retry'}, format='json').status_code == 200


def test_task319_blocked_retry_reanalyses_the_fetched_posting_then_queues_for_maybe(owner, client, tasks, fetch, model, django_capture_on_commit_callbacks):
    job = _blind(owner, model)
    model['answers'] = ['maybe']
    _retry(client, job, django_capture_on_commit_callbacks)
    # Once, with the automatic paths' model (cv_default_choice, as _analyse), on the fetched posting.
    assert len(model['calls']) == 1 and POSTING in model['calls'][0]['prompt'] and model['calls'][0]['choice'] == ('openai', 'gpt-6.1', 'high', 'normal')
    assert JobEvaluation.objects.filter(job=job).order_by('-created_at').first().fit_score == 70
    assert tasks['started'] == [(job.id, 'cv-de')]


def test_task319_a_skip_reanalysis_queues_nothing_and_clears_the_block(owner, client, tasks, fetch, model, django_capture_on_commit_callbacks):
    job = _blind(owner, model)
    model['answers'] = ['skip']
    _retry(client, job, django_capture_on_commit_callbacks)
    assert len(model['calls']) == 1 and tasks['started'] == [] and _items(client) == []


def test_task319_setting_off_prepares_at_once_from_the_earlier_analysis(owner, client, tasks, fetch, model, settings, django_capture_on_commit_callbacks):
    settings.REANALYSE_LATE_TEXT = False
    job = _blind(owner, model)
    _retry(client, job, django_capture_on_commit_callbacks)
    assert model['calls'] == [] and tasks['started'] == [(job.id, 'cv-de')]


def test_task319_a_job_never_evaluated_keeps_todays_retry(owner, client, tasks, fetch, model, django_capture_on_commit_callbacks):
    job = _link_only(owner, 'to_apply')
    application_prep.prepare(job.id, owner)
    _retry(client, job, django_capture_on_commit_callbacks)
    assert model['calls'] == [] and tasks['started'] == [(job.id, 'cv-de')]


def test_task319_evaluate_with_model_on_an_evaluated_link_only_job_runs_the_model_once(owner, client, tasks, fetch, model, django_capture_on_commit_callbacks):
    job = _blind(owner, model, status='new')
    model['answers'] = ['maybe']
    with django_capture_on_commit_callbacks(execute=True):
        response = client.post('/api/jobs/evaluate-with-model/', {'job_ids': [job.id], 'provider': 'ollama', 'model': 'llama3', 'commit': True}, format='json')
    assert response.status_code == 200 and response.data['ok'], response.content
    assert len(model['calls']) == 1 and POSTING in model['calls'][0]['prompt'] and fetch['calls'] == [LINK]


def test_task319_a_failed_reanalysis_blocks_with_retry_and_a_usage_limit_retries_after_the_reset(owner, client, tasks, fetch, model, timers, monkeypatch, django_capture_on_commit_callbacks):
    _at(monkeypatch, '2026-10-19T17:00:00+02:00')
    job = _blind(owner, model)
    model['answers'] = [RecoverableGenerationError('Usage limit reached; resets at 18:51.', usage_limit=True,
                                                   reset_at=datetime.fromisoformat('2026-10-19T18:51:00+02:00')), 'maybe']
    _retry(client, job, django_capture_on_commit_callbacks)
    blocked = {**_blocked(job, 'Re-analysis failed: Usage limit reached; resets at 18:51. Press Retry.'), 'retry_at': '2026-10-19T18:52:00+02:00'}
    assert _items(client) == [blocked] and tasks['started'] == [] and len(model['calls']) == 1
    # TASK-317: once it resets, the blocked Retry runs again -- the text is no longer thin, it re-analyses anyway.
    _at(monkeypatch, '2026-10-19T18:52:00+02:00')
    with django_capture_on_commit_callbacks(execute=True):
        assert application_prep.retry_due() == 1
    assert len(model['calls']) == 2 and tasks['started'] == [(job.id, 'cv-de')]


@pytest.mark.parametrize('path', ['manual', 'refresh'])
def test_task319_a_fetch_that_replaces_thin_text_reanalyses_an_evaluated_job(owner, client, tasks, fetch, model, django_capture_on_commit_callbacks, path):
    job = _blind(owner, model, status='new', text=THIN)
    unevaluated = _link_only(owner, 'new', text=THIN)
    model['answers'] = ['apply']
    with django_capture_on_commit_callbacks(execute=True):
        if path == 'manual':
            for each in (job, unevaluated):
                assert client.post(f'/api/jobs/{each.id}/source-text/live/').status_code == 200
        else:
            assert client.post('/api/jobs/source-text/refresh-due/').data['checked'] == 2
    job.refresh_from_db(); unevaluated.refresh_from_db()
    assert job.original_source_text == POSTING == unevaluated.original_source_text
    # Only the evaluated job is analysed again; the other keeps today's behaviour (nothing runs).
    assert len(model['calls']) == 1 and tasks['started'] == [(job.id, 'cv-de')]
