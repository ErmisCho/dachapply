"""TASK-313: a job that is only a link (or very little text) is read from its URL before it is analysed
and on every fetch, and a job whose preparation was refused shows in the queue as blocked, with a retry
that fetches and prepares again.

Hermetic: fetch_posting_text (posting_fetch's and the name views imported) and the evaluator's model
runner are replaced, so no network and no provider is ever reached.
"""
from unittest.mock import patch

import pytest

from jobradar import views
from jobradar.models import JobLead, UserProfile
from jobradar.services import application_prep, posting_fetch
from jobradar.tests.test_application_prep import POSTING, _job, _req, client, generator, owner, workspace  # noqa: F401 -- fixtures
from jobradar.tests.test_application_prep_queue import ACTION, _items, tasks  # noqa: F401 -- fixtures
from jobradar.tests.test_job_evaluator import OLLAMA_OPTION, evaluation_for

LINK = 'https://jobs.example.test/role'
REFUSED = 'The job has no usable posting text yet.'
FAILED = {'ok': False, 'text': '', 'error': 'The site answered 404 Not Found.', 'final_url': ''}
THIN = 'DevOps Engineer at ACME'
SUBSTANTIAL = ' '.join([POSTING] * 3)  # past JobLead.THIN_SOURCE_CHARS


@pytest.fixture
def fetch(monkeypatch, owner):
    UserProfile.objects.filter(user=owner).update(candidate_profile='EVAL_FIXTURE_PROFILE backend engineer')  # prompts need one
    state = {'calls': [], 'result': {'ok': True, 'text': POSTING, 'error': '', 'final_url': LINK}}

    def fake(url):
        state['calls'].append(url)
        return state['result']
    monkeypatch.setattr(posting_fetch, 'fetch_posting_text', fake)
    monkeypatch.setattr(views, 'fetch_posting_text', fake)  # the job page's manual fetch
    return state


def _link_only(owner, status='new', text=LINK):
    return JobLead.objects.create(company='ACME', title='Python Engineer', status=status, created_by=owner, url=LINK,
                                  original_source_text=text, application_requirements=_req('de'))


def _evaluate(client, job):
    with patch('jobradar.services.job_evaluator.validate_model_capability', return_value=OLLAMA_OPTION), \
         patch('jobradar.services.job_evaluator.run_structured_model', return_value={'evaluations': [evaluation_for(job)]}) as runner:
        response = client.post('/api/jobs/evaluate-with-model/', {'job_ids': [job.id], 'provider': 'ollama', 'model': 'llama3'}, format='json')
    assert response.status_code == 200 and response.data['ok'], response.content
    return runner.call_args[0][0]


# --- AC1: fetch before analysis ------------------------------------------------------------------

def test_a_link_only_job_is_fetched_and_the_model_sees_the_posting(owner, client, fetch):
    job = _link_only(owner)
    assert POSTING in _evaluate(client, job) and fetch['calls'] == [LINK]
    job.refresh_from_db()
    assert job.original_source_text == POSTING and job.source_checked_at and job.source_fetch_error == ''
    # The Analyze-selected prompt reads the fetched text as well.
    other = _link_only(owner)
    response = client.post('/api/prompts/generate/', {'job_ids': [other.id]}, format='json')
    assert response.status_code == 200 and POSTING in response.data['generated_prompt'] and fetch['calls'] == [LINK, LINK]


def test_a_thin_text_is_fetched_and_replaced_before_analysis(owner, client, fetch):
    job = _link_only(owner, text=f'{THIN}\n{LINK}')
    assert POSTING in _evaluate(client, job) and fetch['calls'] == [LINK]
    job.refresh_from_db()
    assert job.original_source_text == POSTING and job.pending_source_text == ''


def test_a_job_with_posting_text_is_not_fetched(owner, client, fetch):
    job = _link_only(owner, text=SUBSTANTIAL)
    _evaluate(client, job)
    assert client.post('/api/prompts/generate/', {'job_ids': [job.id]}, format='json').status_code == 200
    assert fetch['calls'] == []


def test_a_manual_fetch_on_a_thin_job_saves_the_posting_without_review(owner, client, fetch):
    job = _link_only(owner, 'to_apply', text=THIN)
    response = client.post(f'/api/jobs/{job.id}/source-text/live/')
    assert response.status_code == 200 and response.data['staged'] is False and response.data['matches_stored'] is True
    job.refresh_from_db()
    assert job.original_source_text == POSTING and job.pending_source_text == ''


def test_a_manual_fetch_on_a_substantial_job_still_stages_it_for_review(owner, client, fetch):
    page = SUBSTANTIAL + ' Apply by email.'  # longer, so only the threshold keeps the owner's text
    fetch['result'] = {**fetch['result'], 'text': page}
    job = _link_only(owner, 'to_apply', text=SUBSTANTIAL)
    response = client.post(f'/api/jobs/{job.id}/source-text/live/')
    assert response.status_code == 200 and response.data['staged'] is True
    job.refresh_from_db()
    assert job.original_source_text == SUBSTANTIAL and job.pending_source_text == page


def test_a_failed_fetch_is_recorded_and_the_analysis_still_runs(owner, client, fetch):
    fetch['result'] = FAILED
    job = _link_only(owner)
    assert LINK in _evaluate(client, job)
    job.refresh_from_db()
    assert job.source_fetch_error == FAILED['error'] and job.original_source_text == LINK and job.source_checked_at


# --- AC2/AC3: blocked in the queue, and its retry ------------------------------------------------

def _blocked(job, error):
    return {'job_id': job.id, 'company': 'ACME', 'title': 'Python Engineer', 'job_status': job.status, 'key': '', 'label': 'Documents',
            'document': None, 'language': None, 'status': 'blocked', 'position': None, 'progress': 0, 'eta_seconds': None,
            'error': error, 'files': [], 'queued_at': None, 'started_at': None, 'finished_at': None, 'retry_at': None}


def test_a_refused_job_is_listed_as_blocked_but_an_analysis_in_progress_is_not(owner, client, tasks):
    refused, analysing, generated = _link_only(owner, 'to_apply'), _job(owner, 'to_apply'), _job(owner, 'to_apply')
    application_prep.prepare(refused.id, owner)
    application_prep._save(analysing, owner.pk, lambda prep: prep.update(reason=application_prep.ANALYSING, variants={}))
    application_prep._save(generated, owner.pk, lambda prep: prep.update(reason=application_prep.FILES_EXIST, variants={}))
    assert _items(client) == [_blocked(refused, REFUSED)]


def test_retry_on_a_blocked_link_only_job_fetches_and_queues_its_documents(owner, client, tasks, fetch):
    job = _link_only(owner, 'to_apply')
    application_prep.prepare(job.id, owner)
    response = client.post(ACTION, {'job_id': job.id, 'key': '', 'action': 'retry'}, format='json')
    assert response.status_code == 200 and fetch['calls'] == [LINK]
    assert [(item['key'], item['status']) for item in response.json()['items']] == [('cv-de', 'running')]
    assert tasks['started'] == [(job.id, 'cv-de')]


def test_retry_when_the_fetch_fails_keeps_the_job_blocked(owner, client, tasks, fetch):
    fetch['result'] = FAILED
    job = _link_only(owner, 'to_apply')
    application_prep.prepare(job.id, owner)
    response = client.post(ACTION, {'job_id': job.id, 'key': '', 'action': 'retry'}, format='json')
    # TASK-318: the queue says why the link could not be read, not only that the text is missing.
    assert response.status_code == 200 and fetch['calls'] == [LINK] and response.json()['items'] == [_blocked(job, FAILED['error'])]
    job.refresh_from_db()
    assert job.source_fetch_error == FAILED['error'] and tasks['started'] == []
    assert client.post(ACTION, {'job_id': job.id, 'key': '', 'action': 'cancel'}, format='json').status_code == 400


def test_a_blocked_job_whose_page_needs_javascript_shows_the_paste_hint(owner, client, tasks):
    """TASK-318: the Queue tells the owner to paste the text when the link could not be read."""
    job = _link_only(owner, 'to_apply')
    JobLead.objects.filter(pk=job.pk).update(source_fetch_error=posting_fetch.NEEDS_JAVASCRIPT)
    application_prep.prepare(job.id, owner)
    assert _items(client) == [_blocked(job, posting_fetch.NEEDS_JAVASCRIPT)]
