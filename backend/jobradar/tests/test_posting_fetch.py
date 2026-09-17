"""TASK-237: reading the real posting from a job's URL.

Hermetic by construction. Both ends of the network are replaced -- socket.getaddrinfo answers only
for hosts a test registered, and the urllib opener is rebuilt around a fake HTTP handler whose page
table raises KeyError for anything unstaged -- so no test here can reach the internet even by
accident, and the security tests can assert that a refused URL was never dialled at all.
"""
import email.message
import gzip
import io
import socket
import urllib.request
from types import SimpleNamespace
from urllib.error import HTTPError, URLError

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from jobradar.models import JobLead, UserProfile
from jobradar.services import posting_fetch
from jobradar.services.cv_generator import _prompt

# What ChatGPT collected: a summary that reads like a posting but is not one. This is the whole
# defect TASK-237 exists for -- the board shows it as "the original job text".
SUMMARY = 'Backend engineer at ACME Logistics in Berlin. Python and Django, some Kubernetes. Remote possible.'

POSTING_HTML = """<html><head><title>ACME Logistics careers</title>
<style>.hero{color:red}</style></head>
<body><script>window.dataLayer=[{"jobId":42}];</script>
<h1>Senior Backend Engineer (m/w/d)</h1>
<p>ACME Logistics GmbH, Berlin. Vollzeit, unbefristet, Start ab sofort.</p>
<h2>Your tasks</h2>
<ul><li>Design and operate Django services on Kubernetes across three regions.</li>
<li>Own the Postgres schema, migrations and the nightly reconciliation job.</li>
<li>Carry the on-call pager one week in six, together with four other engineers.</li></ul>
<h2>Your profile</h2>
<ul><li>At least five years of professional Python.</li>
<li>German at C1 level and fluent English, both used daily with logistics partners.</li>
<li>Experience with event-driven integration, ideally Kafka.</li></ul>
<p>Application deadline 30 September. Contact jobs@acme.test for questions.</p>
</body></html>"""

JOB_URL = 'http://jobs.acme.test/senior-backend-engineer'
PUBLIC_IP = '93.184.216.34'


def _response(body=b'', code=200, content_type='text/html; charset=utf-8', url='', location='', encoding=''):
    """The parts of an http.client.HTTPResponse urllib actually touches."""
    response = io.BytesIO(body)
    response.code = response.status = code
    response.msg = response.reason = {200: 'OK', 302: 'Found', 403: 'Forbidden'}.get(code, 'OK')
    headers = email.message.Message()
    if content_type:
        headers['Content-Type'] = content_type
    if location:
        headers['Location'] = location
    if encoding:
        headers['Content-Encoding'] = encoding
    response.headers = headers
    response.info = lambda: headers
    response.geturl = lambda: url
    return response


class _FakeHTTPHandler(urllib.request.HTTPHandler):
    def __init__(self, pages):
        super().__init__()
        self.pages = pages
        self.dialled = []

    def http_open(self, req):
        self.dialled.append(req.full_url)
        entry = self.pages[req.full_url]
        if isinstance(entry, Exception):
            raise entry
        return entry()  # a fresh response per dial -- a body is read once and closed


@pytest.fixture
def net(monkeypatch):
    hosts, pages = {}, {}

    def fake_getaddrinfo(host, port, *args, **kwargs):
        if host not in hosts:
            raise socket.gaierror(-2, 'Name or service not known')
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', (hosts[host], port or 80))]

    monkeypatch.setattr(posting_fetch.socket, 'getaddrinfo', fake_getaddrinfo)
    handler = _FakeHTTPHandler(pages)
    # ProxyHandler({}) pins proxies off: otherwise build_opener reads the developer's HTTP_PROXY.
    monkeypatch.setattr(posting_fetch, 'build_opener', lambda *handlers: urllib.request.build_opener(*handlers, urllib.request.ProxyHandler({}), handler))

    def page(url, body='', **kwargs):
        data = body if isinstance(body, bytes) else body.encode('utf-8')
        pages[url] = lambda: _response(data, url=url, **kwargs)

    return SimpleNamespace(host=hosts.__setitem__, page=page, fail=pages.__setitem__, handler=handler)


@pytest.fixture(autouse=True)
def cv_enabled(settings):
    # The endpoint sits behind is_cv_owner, like every other surface of the generation flow, and
    # CODEX_CV_ENABLED defaults to DEBUG -- off under pytest. Turn it on for this file.
    settings.CODEX_CV_ENABLED = True


@pytest.fixture
def owner(db):
    user = User.objects.create_user('posting-owner', password='pw')
    UserProfile.objects.update_or_create(user=user, defaults={'can_generate_cv': True})
    return user


@pytest.fixture
def client(db, owner):
    c = APIClient()
    c.force_authenticate(owner)
    c.user = owner
    return c


@pytest.fixture
def job(db, owner):
    return JobLead.objects.create(company='ACME Logistics', title='Senior Backend Engineer', url=JOB_URL, original_source_text=SUMMARY, created_by=owner)


@pytest.fixture
def live_posting(net):
    net.host('jobs.acme.test', PUBLIC_IP)
    net.page(JOB_URL, POSTING_HTML)
    return net


def test_live_fetch_returns_the_real_body_when_the_stored_text_is_a_summary(client, job, live_posting):
    """AC5: the regression this task exists for -- stored summary, different real posting."""
    data = client.get(f'/api/jobs/{job.id}/source-text/live/').data
    assert data['ok'] is True
    assert 'Own the Postgres schema, migrations and the nightly reconciliation job.' in data['text']
    assert 'Carry the on-call pager one week in six' in data['text']
    assert data['matches_stored'] is False
    assert data['stored_chars'] == len(SUMMARY)
    assert data['chars'] == len(data['text']) > data['stored_chars']
    assert data['final_url'] == JOB_URL
    assert data['url'] == JOB_URL
    assert data['fetched_at'].endswith('+00:00')


def test_fetched_text_is_what_generation_receives_once_the_user_adopts_it(client, job, live_posting):
    """AC2: shown text -> explicit PATCH -> the generation prompt, verbatim."""
    fetched = client.get(f'/api/jobs/{job.id}/source-text/live/').data['text']
    assert client.patch(f'/api/jobs/{job.id}/source-text/', {'original_source_text': fetched}, format='json').status_code == 200
    job.refresh_from_db()
    prompt = _prompt(job, 'CANDIDATE PROFILE', 'CV.tex', 'Letter.tex', 'en', 'en')
    assert fetched in prompt
    assert SUMMARY not in prompt
    assert client.get(f'/api/jobs/{job.id}/source-text/live/').data['matches_stored'] is True


def test_fetch_never_writes_the_stored_text(client, job, live_posting):
    """AC4: adoption stays the user's explicit act -- reading the live page changes nothing."""
    assert client.get(f'/api/jobs/{job.id}/source-text/live/').data['ok'] is True
    stored = JobLead.objects.get(pk=job.pk)
    assert stored.original_source_text == SUMMARY
    assert stored.raw_description == ''


def test_job_without_a_url_is_rejected_before_any_fetch(client, owner, net):
    """AC4: a job with no link keeps working -- it just says so."""
    linkless = JobLead.objects.create(company='ACME', title='Engineer', url='', original_source_text=SUMMARY, created_by=owner)
    response = client.get(f'/api/jobs/{linkless.id}/source-text/live/')
    assert response.status_code == 400
    assert response.data['detail'] == 'This job has no original listing URL.'
    assert net.handler.dialled == []


def test_other_users_job_is_not_found(db, job, net):
    # The stranger clears the capability gate, so what refuses them here is ownership alone.
    stranger_user = User.objects.create_user('posting-stranger', password='pw')
    UserProfile.objects.update_or_create(user=stranger_user, defaults={'can_generate_cv': True})
    stranger = APIClient()
    stranger.force_authenticate(stranger_user)
    response = stranger.get(f'/api/jobs/{job.id}/source-text/live/')
    assert response.status_code == 404
    assert response.data['detail'] == 'Job not found.'
    assert net.handler.dialled == []


def test_an_account_without_cv_capability_cannot_make_the_server_fetch_anything(db, job, net):
    """The panel is only rendered inside the CV generation flow; the endpoint matches that set,
    so no other account can use this server as an outbound fetcher."""
    plain = APIClient()
    plain.force_authenticate(User.objects.create_user('no-cv', password='pw'))
    response = plain.get(f'/api/jobs/{job.id}/source-text/live/')
    assert response.status_code == 404
    assert response.data['detail'] == 'Not found.'
    assert net.handler.dialled == []


def test_blocked_posting_reports_the_http_status(client, job, net):
    """AC3."""
    net.host('jobs.acme.test', PUBLIC_IP)
    net.fail(JOB_URL, HTTPError(JOB_URL, 403, 'Forbidden', email.message.Message(), None))
    data = client.get(f'/api/jobs/{job.id}/source-text/live/').data
    assert data['ok'] is False
    assert data['error'] == 'The site answered 403 Forbidden.'


def test_timeout_reports_the_timeout(client, job, net):
    """AC3."""
    net.host('jobs.acme.test', PUBLIC_IP)
    net.fail(JOB_URL, URLError(TimeoutError('timed out')))
    assert client.get(f'/api/jobs/{job.id}/source-text/live/').data['error'] == 'No response within 10 seconds.'


def test_dead_domain_reports_the_dns_failure(client, job, net):
    """AC3: nothing registered for jobs.acme.test, so resolution fails."""
    data = client.get(f'/api/jobs/{job.id}/source-text/live/').data
    assert data['ok'] is False
    assert data['error'] == 'The address could not be resolved.'
    assert net.handler.dialled == []


def test_non_html_content_type_is_refused_by_name(client, job, net):
    """AC3."""
    net.host('jobs.acme.test', PUBLIC_IP)
    net.page(JOB_URL, '%PDF-1.7 binary', content_type='application/pdf')
    assert client.get(f'/api/jobs/{job.id}/source-text/live/').data['error'] == 'The link returned application/pdf, not a readable web page.'


def test_javascript_only_page_says_so(client, job, net):
    net.host('jobs.acme.test', PUBLIC_IP)
    net.page(JOB_URL, '<html><body><div id="root"></div><script>render()</script></body></html>')
    assert client.get(f'/api/jobs/{job.id}/source-text/live/').data['error'] == 'The page returned no readable text — it may require JavaScript.'


def test_url_resolving_to_a_private_address_is_refused_without_dialling(client, owner, net):
    """Security floor: the container can see its own network and the metadata service."""
    for address in ('127.0.0.1', '10.0.0.7', '169.254.169.254'):
        internal = JobLead.objects.create(company='ACME', title='Engineer', url=f'http://internal.acme.test/{address}', original_source_text=SUMMARY, created_by=owner)
        net.host('internal.acme.test', address)
        data = client.get(f'/api/jobs/{internal.id}/source-text/live/').data
        assert data['ok'] is False, address
        assert data['error'] == 'Refused: that link resolves to a private network address.'
    assert net.handler.dialled == []


def test_redirect_from_a_public_host_into_a_private_address_is_refused(client, job, net):
    """The hop the naive version misses: urllib follows redirects silently."""
    net.host('jobs.acme.test', PUBLIC_IP)
    net.host('metadata.acme.test', '169.254.169.254')
    net.page(JOB_URL, '', code=302, location='http://metadata.acme.test/latest/meta-data/')
    data = client.get(f'/api/jobs/{job.id}/source-text/live/').data
    assert data['ok'] is False
    assert data['error'] == 'Refused: that link resolves to a private network address.'
    assert net.handler.dialled == [JOB_URL]


def test_gzipped_page_is_unpacked_instead_of_being_served_as_garbage(client, job, net):
    """Regression for a live defect: https://www.python.org/jobs/ answers content-encoding: gzip to
    a request that never asked for it, and the first version of this reader decoded those bytes as
    text and returned 10664 characters of U+FFFD as 'the real posting'."""
    net.host('jobs.acme.test', PUBLIC_IP)
    net.page(JOB_URL, gzip.compress(POSTING_HTML.encode('utf-8')), encoding='gzip')
    data = client.get(f'/api/jobs/{job.id}/source-text/live/').data
    assert data['ok'] is True, data.get('error')
    assert '�' not in data['text']
    assert 'Own the Postgres schema, migrations and the nightly reconciliation job.' in data['text']


def test_brotli_page_says_it_cannot_be_opened(client, job, net):
    net.host('jobs.acme.test', PUBLIC_IP)
    net.page(JOB_URL, 'binary brotli bytes', encoding='br')
    assert client.get(f'/api/jobs/{job.id}/source-text/live/').data['error'] == 'The page arrived br-compressed, which this reader cannot open.'


def test_script_and_style_content_never_reaches_the_text():
    text = posting_fetch.extract_text(POSTING_HTML)
    assert 'color:red' not in text
    assert 'dataLayer' not in text
    assert text.startswith('Senior Backend Engineer (m/w/d)')
    assert 'At least five years of professional Python.' in text
