"""TASK-282: round trips per logged-in request on the three hot endpoints.

Against remote Neon every query is ~35 ms, so the query COUNT is the latency. These tests pin it
exactly (a regression fails, an improvement forces a deliberate update) and snapshot each JSON
response against a file produced from the pre-TASK-282 code, so fewer queries cannot mean a
different answer.

The client logs in through a real session (app_sessionid, SplitAdminSessionMiddleware) rather
than force_authenticate, because the session and user lookups are part of what is being counted.
USAGE_RECORD_ASYNC is False under settings_test, so UserUsageMiddleware's counters run inline and
are counted too; the *_EXCL_USAGE numbers are with that middleware's writes patched out (in
production they run on a background thread after the response).

Regenerate the snapshot (only when a response is meant to change):
    UPDATE_QUERY_SNAPSHOT=1 uv run pytest jobradar/tests/test_query_counts.py
"""
import datetime
import json
import os
from pathlib import Path
from unittest import mock

import pytest
from django.contrib.auth.models import User
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from jobradar.middleware import UserUsageMiddleware
from jobradar.models import ApplicationNote, FollowUp, JobEvaluation, JobLead, MailboxMessage, MailboxRun, UserProfile

SNAPSHOT = Path(__file__).parent / 'fixtures' / 'query_counts_snapshot.json'
BOARD_URL = '/api/jobs/?status=new,reviewed,to_apply,applied,interview&ordering=recommended&board=1'
T0 = timezone.make_aware(datetime.datetime(2026, 10, 1, 12, 0))


@pytest.fixture
def owner_client(db):
    owner = User.objects.create_user('qc-owner', email='owner@example.test', password='pw', is_staff=True, pk=501)
    friend = User.objects.create_user('qc-friend', email='friend@example.test', password='pw', pk=502)
    UserProfile.objects.create(user=owner, candidate_profile='Backend engineer, Python and Django.', board_sort_keys='')
    statuses = ['new', 'reviewed', 'to_apply', 'applied', 'interview', 'new']
    run = MailboxRun.objects.create(pk=1)
    for i, status in enumerate(statuses, start=1):
        job = JobLead.objects.create(pk=900 + i, company=f'Company {i}', title=f'Engineer {i}', url=f'https://jobs.example.test/{i}',
                                     status=status, created_by=owner, raw_description=f'Posting {i}', location='Berlin')
        if i != 6:  # one unanalysed job
            JobEvaluation.objects.create(pk=700 + i, job=job, fit_score=50 + i * 5, priority=['high', 'medium', 'low'][i % 3],
                                         recommendation='apply', summary=f'Summary {i}', required_skills=['Python', 'Django'],
                                         matched_skills=['Python'], missing_skills=['Kubernetes'], nice_to_have_skills=['Go'])
        if i % 2:
            ApplicationNote.objects.create(pk=800 + i, job=job, note=f'Note for job {i}\n\nmore text', created_by=owner)
        if i == 4:
            FollowUp.objects.create(pk=600 + i, job=job, follow_up_date=datetime.date(2026, 10, 20), reason='Ping recruiter')
            MailboxMessage.objects.create(pk=400 + i, run=run, uid=i, sender='hr@example.test', subject='Re: application', matched_job=job)
    # One job handed to a friend: the board list projects it down to the submission row.
    JobLead.objects.create(pk=950, company='Friend Co', title='Friend role', url='https://jobs.example.test/friend',
                           status='new', created_by=owner, submitted_for=friend)
    # auto_now / auto_now_add would otherwise put the wall clock into the snapshot.
    for model in (JobLead, JobEvaluation, ApplicationNote, FollowUp):
        fields = {f.name: T0 for f in model._meta.fields if f.name in ('created_at', 'updated_at')}
        model.objects.update(**fields)
    client = Client()
    client.force_login(owner)
    client.cookies['app_sessionid'] = client.cookies['sessionid'].value
    del client.cookies['sessionid']
    client.get('/api/auth/me/')  # warm the visitor cookie so every counted request is a repeat visit
    return client


ENDPOINTS = {
    'me': '/api/auth/me/',
    'job_detail': '/api/jobs/904/',
    'board_list': BOARD_URL,
}


def measure(client, url, usage=True):
    with mock.patch.object(UserUsageMiddleware, 'record_usage_values') if not usage else _nullcontext():
        with CaptureQueriesContext(connection) as ctx:
            response = client.get(url)
    assert response.status_code == 200, response.content
    return response, [q['sql'] for q in ctx.captured_queries]


class _nullcontext:
    def __enter__(self): return self
    def __exit__(self, *exc): return False


# Exact (total, excluding usage middleware) counts. Before TASK-282 they were me (12, 4),
# job_detail (13, 5), board_list (14, 6). Excluding usage, what is left is the floor for this
# auth/session setup: session row + auth_user on every request, then
#   me:         userprofile (with both friend links joined)
#   job_detail: joblead + its evaluations (prefetch)
#   board_list: userprofile (saved status order) + joblead + evaluations (prefetch)
# The usage middleware adds 4 (one F() UPDATE per counter; it was get_or_create + UPDATE = 8).
EXPECTED = {
    'me': (7, 3),
    'job_detail': (8, 4),
    'board_list': (9, 5),
}


@pytest.mark.parametrize('name', list(ENDPOINTS))
def test_query_counts_are_pinned(owner_client, name):
    _, with_usage = measure(owner_client, ENDPOINTS[name], usage=True)
    _, without_usage = measure(owner_client, ENDPOINTS[name], usage=False)
    if os.environ.get('PRINT_QUERIES'):
        print(f'\n=== {name}: {len(with_usage)} total, {len(without_usage)} excluding usage middleware')
        for sql in without_usage:
            print('   ', sql[:300])
    assert (len(with_usage), len(without_usage)) == EXPECTED[name], without_usage


def test_responses_match_the_pre_task_282_snapshot(owner_client):
    bodies = {name: json.loads(measure(owner_client, url, usage=False)[0].content) for name, url in ENDPOINTS.items()}
    if os.environ.get('UPDATE_QUERY_SNAPSHOT'):
        SNAPSHOT.write_text(json.dumps(bodies, indent=1, sort_keys=False, ensure_ascii=False) + '\n', encoding='utf-8')
    assert bodies == json.loads(SNAPSHOT.read_text(encoding='utf-8'))


@pytest.mark.parametrize('debug, pooled, cached', [(True, True, True), (True, False, False), (False, True, False), (False, False, False)])
def test_cached_sessions_only_on_the_pooled_local_runtime(debug, pooled, cached):
    from config.settings import cached_sessions_enabled
    db = {'OPTIONS': {'pool': {'min_size': 1}}} if pooled else {}
    assert cached_sessions_enabled(db, debug) is cached


@pytest.fixture
def cached_sessions(settings):
    settings.SESSION_ENGINE = 'django.contrib.sessions.backends.cached_db'
    settings.SESSION_CACHE_ALIAS = 'sessions'
    settings.CACHES = {**settings.CACHES, 'sessions': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'qc-sessions'}}


def test_cached_sessions_skip_the_session_query_and_logout_still_ends_the_session(cached_sessions, owner_client):
    _, warm = measure(owner_client, '/api/auth/me/', usage=False)
    assert not any('django_session' in sql for sql in warm)
    assert len(warm) == EXPECTED['me'][1] - 1
    replay = Client()
    replay.cookies['app_sessionid'] = owner_client.cookies['app_sessionid'].value
    assert replay.get('/api/auth/me/').status_code == 200
    owner_client.post('/api/auth/logout/')
    assert replay.get('/api/auth/me/').status_code == 403
