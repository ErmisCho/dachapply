"""Automatic retries share failures; explicit user retries remain fresh."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest

from jobradar.models import JobLead
from jobradar.services import application_prep, cv_tasks, posting_fetch
from jobradar.tests.test_application_prep import client, generator, owner, workspace  # noqa: F401
from jobradar.tests.test_link_only_prep import ACTION, FAILED, LINK, _link_only, fetch  # noqa: F401


def test_analysis_and_document_retries_share_a_failed_fetch(owner, fetch):
    job = _link_only(owner)
    fetch['result'] = FAILED
    posting_fetch.fetch_missing_sources([job])
    checked_at = job.source_checked_at
    posting_fetch.fetch_missing_sources([job])
    assert job.source_checked_at == checked_at
    assert fetch['calls'] == [LINK]
    cv_tasks._retry_missing_source(job)
    assert fetch['calls'] == [LINK]
    assert job.source_fetch_error == FAILED['error']


def test_cooldown_expires_and_explicit_retry_bypasses_it(owner, client, fetch, monkeypatch, workspace):
    clock = [100.0]
    monkeypatch.setattr(posting_fetch, 'monotonic', lambda: clock[0], raising=False)
    job = _link_only(owner, 'to_apply')
    fetch['result'] = FAILED
    posting_fetch.fetch_missing_sources([job])
    clock[0] += 599
    posting_fetch.fetch_missing_sources([job])
    assert len(fetch['calls']) == 1
    application_prep.prepare(job.pk, owner)
    assert client.post(ACTION, {'job_id': job.pk, 'key': '', 'action': 'retry'}, format='json').status_code == 200
    assert len(fetch['calls']) == 2
    clock[0] += 601
    posting_fetch.fetch_missing_sources([job])
    assert len(fetch['calls']) == 3


def test_a_newer_manual_check_invalidates_the_older_automatic_failure(owner, client, fetch):
    job = _link_only(owner)
    fetch['result'] = FAILED
    posting_fetch.fetch_missing_sources([job])
    first_check = job.source_checked_at
    fetch['result'] = {**FAILED, 'error': 'A newer failure'}
    assert client.post(f'/api/jobs/{job.pk}/source-text/live/').status_code == 200
    job.refresh_from_db()
    assert job.source_checked_at > first_check
    posting_fetch.fetch_missing_sources([job])
    assert len(fetch['calls']) == 3 and job.source_fetch_error == 'A newer failure'
    assert job.source_checked_at > first_check


def test_changed_url_or_text_invalidates_failure_and_pending_choice_is_untouched(owner, fetch):
    job = _link_only(owner)
    fetch['result'] = FAILED
    posting_fetch.fetch_missing_sources([job])
    job.url += '?changed=1'; job.save(update_fields=['url'])
    posting_fetch.fetch_missing_sources([job])
    assert len(fetch['calls']) == 2
    job.original_source_text = 'A changed short posting'; job.save(update_fields=['original_source_text'])
    posting_fetch.fetch_missing_sources([job])
    assert len(fetch['calls']) == 3
    job.pending_source_text = 'A pending choice'; job.save(update_fields=['pending_source_text'])
    posting_fetch.fetch_missing_sources([job])
    assert len(fetch['calls']) == 3 and job.pending_source_text == 'A pending choice'


def test_simultaneous_equivalent_retrievals_share_the_network_call(monkeypatch):
    entered, release = Event(), Event()
    calls = []
    job = JobLead(pk=42, created_by_id=7, url=LINK, original_source_text=LINK)
    def download(url):
        calls.append(url); entered.set()
        assert release.wait(5)
        return FAILED
    monkeypatch.setattr(posting_fetch, 'fetch_posting_text', download)
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = [pool.submit(posting_fetch.fetch_job_posting, job) for _ in range(6)]
        assert entered.wait(5)
        release.set()
        results = [f.result(5) for f in futures]
        assert all(result['error'] == FAILED['error'] and result['ok'] is False for result in results)
        assert len({result['checked_at'] for result in results}) == 1
    assert calls == [LINK]
