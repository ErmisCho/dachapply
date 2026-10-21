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
import re
from pathlib import Path
from unittest import mock

import pytest
from django.contrib.auth.models import User
from django.db import connection, models
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
    # JobLead.save() stamps applied_at with today's date; pin it to the snapshot's.
    JobLead.objects.filter(applied_at__isnull=False).update(applied_at=datetime.date(2026, 10, 13))
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
# TASK-283.2: the second (excluding-usage) board request is warm -- every row comes from
# CACHES['board_rows'], so joblead + evaluations become one id/stamp query (was (9, 5)).
EXPECTED = {
    'me': (7, 3),
    'job_detail': (8, 4),
    'board_list': (9, 4),
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


def test_me_and_job_detail_read_only_what_they_serialize(owner_client):
    """TASK-282 part 2: the counts above cannot see bytes. /me used to load the whole profile row
    (~160 KB of CV/profile text, 70 ms of a 154 ms request on Neon) and the detail ran the board's six
    correlated subqueries for one row whose serializer reads none of them."""
    _, me = measure(owner_client, ENDPOINTS['me'], usage=False)
    [profile_sql] = [sql for sql in me if 'FROM "jobradar_userprofile"' in sql]
    selected = re.sub(r'SUBSTR\("jobradar_userprofile"\."\w+", 1, 65\)', '', profile_sql)  # the _profile_has_text heads
    text_fields = [f.name for f in UserProfile._meta.fields if isinstance(f, models.TextField)]
    assert [f for f in text_fields if f'"jobradar_userprofile"."{f}"' in selected] == []
    _, detail = measure(owner_client, ENDPOINTS['job_detail'], usage=False)
    [job_sql] = [sql for sql in detail if 'FROM "jobradar_joblead"' in sql]
    assert '(SELECT' not in job_sql and 'EXISTS' not in job_sql


@pytest.mark.parametrize('candidate_profile, missing, extra_query', [
    ('x' * 1000, False, 0),              # long, decided by its head
    (' ' * 100 + 'Engineer', False, 1),  # long and opens with whitespace: the full read decides
    (' ' * 100, True, 1),
    ('"   "', True, 0),                  # JSON-quoted blank (old sqlite schemas) still reads as blank
    ('', True, 0),
])
def test_me_candidate_profile_missing_from_field_heads(owner_client, candidate_profile, missing, extra_query):
    UserProfile.objects.filter(user_id=501).update(candidate_profile=candidate_profile)
    response, queries = measure(owner_client, ENDPOINTS['me'], usage=False)
    assert json.loads(response.content)['candidate_profile_missing'] is missing
    assert len(queries) == EXPECTED['me'][1] + extra_query


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


@pytest.fixture
def local_runtime(cached_sessions, settings):
    """TASK-283.1: everything config/settings.py turns on under cached_sessions_enabled."""
    settings.CACHES = {**settings.CACHES, 'local': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'qc-local'}}
    settings.AUTHENTICATION_BACKENDS = ['jobradar.local_cache.CachedModelBackend']
    from django.core.cache import caches
    caches['local'].clear()


# Warm requests on the local runtime: session, user and board settings all come from the process,
# so what is left is the endpoint's own data (+ the same 4 usage UPDATEs, async there).
# TASK-283.2: for the board that is the single id/stamp query, all rows cached (was (6, 2)).
EXPECTED_LOCAL = {
    'me': (5, 1),
    'job_detail': (6, 2),
    'board_list': (5, 1),
}


@pytest.mark.parametrize('name', list(ENDPOINTS))
def test_query_counts_on_the_local_runtime_are_pinned(local_runtime, owner_client, name):
    owner_client.get(ENDPOINTS[name])  # fills the caches a fresh process would fill once
    _, with_usage = measure(owner_client, ENDPOINTS[name], usage=True)
    _, without_usage = measure(owner_client, ENDPOINTS[name], usage=False)
    assert (len(with_usage), len(without_usage)) == EXPECTED_LOCAL[name], without_usage


def test_local_runtime_responses_match_the_snapshot(local_runtime, owner_client):
    for name, url in ENDPOINTS.items():
        owner_client.get(url)
        assert json.loads(measure(owner_client, url, usage=False)[0].content) == json.loads(SNAPSHOT.read_text(encoding='utf-8'))[name]


def _replay(client):
    """A second browser holding the same session cookie."""
    replay = Client()
    replay.cookies['app_sessionid'] = client.cookies['app_sessionid'].value
    return replay


def test_local_runtime_password_change_rejects_the_old_session_next_request(local_runtime, owner_client):
    other = _replay(owner_client)
    assert other.get(BOARD_URL).status_code == 200  # user now cached
    response = owner_client.post('/api/auth/change-password/', {'current_password': 'pw', 'new_password': 'a-much-Longer-pw-2026'}, content_type='application/json')
    assert response.status_code == 200, response.content
    assert other.get(BOARD_URL).status_code == 403
    assert owner_client.get(BOARD_URL).status_code == 200  # change_password re-logs this session in


def test_local_runtime_logout_makes_the_next_request_anonymous(local_runtime, owner_client):
    assert owner_client.get(BOARD_URL).status_code == 200
    owner_client.post('/api/auth/logout/')
    assert owner_client.get(BOARD_URL).status_code == 403


def test_local_runtime_deactivation_rejects_the_next_request(local_runtime, owner_client):
    assert owner_client.get(BOARD_URL).status_code == 200
    owner = User.objects.get(pk=501)
    owner.is_active = False
    owner.save()
    assert owner_client.get(BOARD_URL).status_code == 403


def test_local_runtime_board_uses_profile_edits_on_the_next_request(local_runtime, owner_client):
    url = '/api/jobs/?status=new,reviewed,to_apply,applied,interview&board=1'  # no ?ordering=: the saved one applies
    before = [row['id'] for row in json.loads(owner_client.get(url).content)]
    # TASK-329: ascending, so it still differs from the status-grouped default.
    response = owner_client.patch('/api/profile/', {'board_sort_keys': 'fit_score'}, content_type='application/json')
    assert response.status_code == 200, response.content
    by_score = [row['id'] for row in json.loads(owner_client.get(url).content)]
    assert by_score != before
    response = owner_client.patch('/api/profile/', {'board_sort_keys': '', 'board_status_order': 'interview,applied'}, content_type='application/json')
    assert response.status_code == 200, response.content
    by_status = [row['id'] for row in json.loads(owner_client.get(url).content)]
    assert by_status != before and by_status != by_score
    assert by_status.index(905) < by_status.index(904) < by_status.index(901)  # interview, applied, then the rest


def test_cached_sessions_skip_the_session_query_and_logout_still_ends_the_session(cached_sessions, owner_client):
    _, warm = measure(owner_client, '/api/auth/me/', usage=False)
    assert not any('django_session' in sql for sql in warm)
    assert len(warm) == EXPECTED['me'][1] - 1
    replay = Client()
    replay.cookies['app_sessionid'] = owner_client.cookies['app_sessionid'].value
    assert replay.get('/api/auth/me/').status_code == 200
    owner_client.post('/api/auth/logout/')
    assert replay.get('/api/auth/me/').status_code == 403


def test_server_timing_header_counts_the_queries_for_logged_in_users_only(owner_client):
    """TASK-283.3: the header reports the same query count the tests above pin."""
    response, queries = measure(owner_client, BOARD_URL, usage=False)
    assert f'desc="{len(queries)} queries"' in response['Server-Timing'], response['Server-Timing']
    assert 'Server-Timing' not in Client().get('/api/health/')
