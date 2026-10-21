"""TASK-281: the local runtime gets Django's native psycopg pool; the deployed site does not; and
the usage middleware's writes can run after the response instead of before it.

Hermetic: dj_database_url.parse only builds a dict and with_db_pool only edits it -- no connection,
no pool object, nothing leaves the process. The latency criterion (AC1) and the idle-drop one (AC4)
need the real Neon database and are measured there, not simulated here.
"""
import threading
import time
from datetime import date as dt_date, datetime

import dj_database_url
import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from config.settings import with_db_pool
from jobradar.middleware import UserUsageMiddleware
from jobradar.services.analytics import VISITOR_COOKIE_NAME, clean_visitor_id

PG_URL = 'postgres://user:pass@db.example.invalid:5432/app'


def parsed(url=PG_URL):
    return dj_database_url.parse(url, conn_max_age=600, conn_health_checks=True)


@pytest.mark.parametrize('debug, db_pool, pooled', [
    (True, None, True),     # local DEBUG runtime: on by default
    (False, None, False),   # deployed site: unchanged by default
    (False, '1', True),     # ...unless explicitly enabled
    (True, '0', False),     # and the local default can be switched off
])
def test_pool_follows_debug_unless_db_pool_is_set(monkeypatch, debug, db_pool, pooled):
    if db_pool is None:
        monkeypatch.delenv('DB_POOL', raising=False)
    else:
        monkeypatch.setenv('DB_POOL', db_pool)

    db = with_db_pool(parsed(), debug)

    assert ('pool' in db.get('OPTIONS', {})) is pooled
    # Django raises "Pooling doesn't support persistent connections." for any other value.
    assert db['CONN_MAX_AGE'] == (0 if pooled else 600)
    # Kept on: it is what makes Django give the pool ConnectionPool.check_connection.
    assert db['CONN_HEALTH_CHECKS'] is True
    # TASK-282: the pooled runtime's backend swaps that check for check_unless_recent.
    assert db['ENGINE'] == ('config.pooled_postgres' if pooled else 'django.db.backends.postgresql')


def test_pool_is_never_added_to_a_non_postgres_database(monkeypatch):
    monkeypatch.setenv('DB_POOL', '1')

    db = with_db_pool(parsed('sqlite:///tmp.db'), True)

    assert 'pool' not in db.get('OPTIONS', {})


def test_usage_is_recorded_after_the_response_from_plain_values(db, settings, monkeypatch):
    """TASK-281: the usage writes (~8-10 Neon round trips) must not hold the response back."""
    user = User.objects.create_user('usage-async@example.test', password='pw')
    client = APIClient()
    client.cookies[VISITOR_COOKIE_NAME] = 'a' * 32
    assert client.post('/api/auth/login/', {'username': user.username, 'password': 'pw'}, format='json').status_code == 200

    settings.USAGE_RECORD_ASYNC = True
    release, finished, received = threading.Event(), threading.Event(), []

    def blocking_recorder(self, *args):
        received.append(args)
        release.wait(5)
        finished.set()

    monkeypatch.setattr(UserUsageMiddleware, 'record_usage_values', blocking_recorder)

    try:
        client.get('/api/auth/me/')
        # Run synchronously, the recorder would have finished (on its 5 s timeout) before the
        # response came back. Still blocked means the response did not wait for it.
        assert not finished.is_set()
    finally:
        release.set()
    assert finished.wait(5)

    [(now, date, visitor_id, user_id)] = received
    assert isinstance(now, datetime) and isinstance(date, dt_date)
    assert (visitor_id, user_id) == (clean_visitor_id('a' * 32), user.pk)


def test_background_usage_recording_holds_at_most_one_connection(db, settings, monkeypatch):
    """2026-10-17: a Thread per request let slow usage writes take all 8 pool connections."""
    settings.USAGE_RECORD_ASYNC = True
    lock, running, peak, done = threading.Lock(), [0], [0], threading.Semaphore(0)

    def slow_recorder(self, *args):
        with lock:
            running[0] += 1
            peak[0] = max(peak[0], running[0])
        time.sleep(0.05)
        with lock:
            running[0] -= 1
        done.release()

    monkeypatch.setattr(UserUsageMiddleware, 'record_usage_values', slow_recorder)
    client = APIClient()
    client.cookies[VISITOR_COOKIE_NAME] = 'c' * 32  # TASK-330: only a returning visitor is recorded
    for _ in range(6):
        client.get('/api/auth/me/')
    assert all(done.acquire(timeout=5) for _ in range(6))
    assert peak[0] == 1


def test_a_request_without_the_visitor_cookie_gets_it_but_is_not_recorded(db, settings):
    """TASK-330: a cookieless local poller hit / every 2 s and minted a visitor row per hit (371,715 by
    2026-10-21, most of Neon's 5 GB monthly transfer). Only a request that brought the cookie back counts."""
    from jobradar.models import SiteDailyUsage, SiteVisitor, UserDailyUsage, VisitorDailyUsage
    settings.USAGE_RECORD_ASYNC = False
    client = APIClient()
    first = client.get('/')
    assert first.cookies[VISITOR_COOKIE_NAME].value
    tables = (SiteVisitor, VisitorDailyUsage, SiteDailyUsage, UserDailyUsage)
    assert [model.objects.count() for model in tables] == [0, 0, 0, 0]
    client.get('/')  # the browser sends the cookie back: now it is a visitor
    assert SiteVisitor.objects.get().visitor_id == clean_visitor_id(first.cookies[VISITOR_COOKIE_NAME].value)


def test_a_failing_background_recorder_is_swallowed(monkeypatch):
    def failing_recorder(self, *args):
        raise RuntimeError('database went away')

    monkeypatch.setattr(UserUsageMiddleware, 'record_usage_values', failing_recorder)
    returned = []

    def run():
        UserUsageMiddleware(None).record_usage_in_background(None, None, 'v', None)
        returned.append(True)  # only reached if the error did not escape

    thread = threading.Thread(target=run)
    thread.start()
    thread.join(5)

    assert returned == [True]


def test_pooled_backend_checks_only_connections_idle_for_a_while(monkeypatch):
    """TASK-282: the check is an empty query, one Neon round trip per request. Building the pool
    opens nothing (open=False), so this stays hermetic."""
    from config.pooled_postgres import base as pooled

    monkeypatch.setenv('DB_POOL', '1')
    wrapper = pooled.DatabaseWrapper({**with_db_pool(parsed(), True), 'TIME_ZONE': None, 'AUTOCOMMIT': True}, alias='t282-pool')
    try:
        assert wrapper.pool._check is pooled.check_unless_recent
    finally:
        wrapper.close_pool()

    class Conn:
        autocommit = True
        def __init__(self): self.checks = 0
        def execute(self, sql): self.checks += 1

    clock = [1000.0]
    monkeypatch.setattr(pooled, 'monotonic', lambda: clock[0])
    conn = Conn()
    pooled.check_unless_recent(conn)       # never handed out: checked
    clock[0] += pooled.RECENT - 1
    pooled.check_unless_recent(conn)       # used a moment ago: no round trip
    clock[0] += pooled.RECENT
    pooled.check_unless_recent(conn)       # idle long enough for Neon to have dropped it
    assert conn.checks == 2
