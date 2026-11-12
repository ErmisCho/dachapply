# TASK-371: no network; count retrievals across analysis and document variants.
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from types import SimpleNamespace

import pytest

from jobradar.services import cv_tasks, posting_fetch as fetch


@pytest.fixture(autouse=True)
def decisions():
    fetch._fetch_decisions.clear()
    yield
    fetch._fetch_decisions.clear()


def job(**changes):
    return SimpleNamespace(pk=371,created_by_id=1,url='https://example.test/job',source_text='',pending_source_text='',**changes)


def test_failure_workload_expiry_manual_and_invalidation(monkeypatch):
    current=job(); calls=[]; clock=[0]
    monkeypatch.setattr(fetch.time,'monotonic',lambda:clock[0])
    monkeypatch.setattr(fetch,'fetch_posting_text',lambda url: calls.append(url) or fetch._failed('Unavailable.'))
    for _ in range(6):
        assert not fetch.fetch_job_posting(current)['ok']
    assert len(calls)==1  # six analyses/variants previously made six attempts
    assert 'Next automatic try after' in fetch.fetch_job_posting(current)['error']
    assert 'Retry fetches now' in fetch.fetch_job_posting(current)['error']
    fetch.fetch_job_posting(current,force=True)
    assert len(calls)==2
    clock[0]=fetch.FETCH_COOLDOWN_SECONDS+1
    fetch.fetch_job_posting(current)
    assert len(calls)==3
    for field,value in [('url','https://example.test/new'),('source_text','Updated posting'),('pending_source_text','Accepted candidate'),('created_by_id',2)]:
        setattr(current,field,value)
        fetch.fetch_job_posting(current)
    assert len(calls)==7
    monkeypatch.setattr(fetch,'fetch_posting_text',lambda url:{'ok':True,'text':'Recovered'})
    assert fetch.fetch_job_posting(current,force=True)['ok']
    assert fetch.fetch_job_posting(current)['ok']


def test_equivalent_concurrent_requests_share_retrieval(monkeypatch):
    entered=Event(); release=Event(); calls=[]
    def retrieve(url):
        calls.append(url); entered.set()
        assert release.wait(5)
        return fetch._failed('Unavailable.')
    monkeypatch.setattr(fetch,'fetch_posting_text',retrieve)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first=pool.submit(fetch.fetch_job_posting,job())
        assert entered.wait(5)
        second=pool.submit(fetch.fetch_job_posting,job())
        release.set()
        assert first.result()==second.result()
    assert len(calls)==1


def test_analysis_and_document_variants_share_failure(db,monkeypatch):
    from jobradar.models import JobLead
    current=JobLead.objects.create(company='ACME',title='Engineer',url='https://example.test/job')
    calls=[]
    def retrieve(url):
        calls.append(url)
        return fetch._failed('Unavailable.')
    monkeypatch.setattr(fetch,'fetch_posting_text',retrieve)
    monkeypatch.setattr(cv_tasks,'fetch_posting_text',retrieve)
    for _ in range(3):
        fetch.fetch_missing_sources([current])
        cv_tasks._retry_missing_source(current)
    assert len(calls)==1
    current.refresh_from_db()
    assert 'Next automatic try after' in current.source_fetch_error
