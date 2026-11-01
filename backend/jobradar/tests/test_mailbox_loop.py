"""TASK-276: one tick of the in-app mailbox loop runs the check_mailbox logic, cadence-gated."""
from django.contrib.auth import get_user_model

from jobradar.services import mailbox, mailbox_loop
from jobradar.services.mailbox import MailboxCheckInProgress, pending_mailbox_check_request, queue_mailbox_check_request


def test_tick_runs_the_cadence_gated_check(db, monkeypatch):
    calls = []
    monkeypatch.setattr(mailbox, 'run_check', lambda force=False: calls.append(force))
    mailbox_loop.tick()
    assert calls == [False]


def test_tick_handles_a_pending_manual_request_first(db, monkeypatch):
    calls = []
    monkeypatch.setattr(mailbox, 'run_check', lambda force=False: calls.append(force))
    request = queue_mailbox_check_request(get_user_model().objects.create_user('owner', password='pw'))
    mailbox_loop.tick()
    request.refresh_from_db()
    assert calls == [True]
    assert request.handled_at is not None
    assert pending_mailbox_check_request() is None


def test_tick_never_raises(db, monkeypatch):
    def boom(force=False):
        raise RuntimeError('gmail down')
    monkeypatch.setattr(mailbox, 'run_check', boom)
    mailbox_loop.tick()

    def busy(force=False):
        raise MailboxCheckInProgress('A mailbox check is already running.')
    monkeypatch.setattr(mailbox, 'run_check', busy)
    mailbox_loop.tick()


# --- TASK-347: sleep until the next check is due; no database between due checks or outside the window ---

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from jobradar.models import MailboxRun, ScheduledTaskRun
from jobradar.services.prompt_builder import user_profile_settings

VIENNA = ZoneInfo('Europe/Vienna')


def _local(day, hour, minute=0, second=0):
    return datetime(2026, 11, day, hour, minute, second, tzinfo=VIENNA)  # clear of the 25 Oct DST change


@pytest.mark.parametrize('now, last_run, window, expected', [
    # inside the window: last run + cadence
    (_local(4, 10, 30), _local(4, 10), (time(8), time(20)), _local(4, 11, 0, 5)),
    # due after the window closes: tomorrow's opening, not a wake at 20:30
    (_local(4, 19, 31), _local(4, 19, 30), (time(8), time(20)), _local(5, 8)),
    # before the window opens: today's opening
    (_local(4, 6), _local(3, 19), (time(8), time(20)), _local(4, 8)),
    # window crossing midnight, due after it closes at 06:00: the 22:00 opening the same day
    (_local(4, 5, 31), _local(4, 5, 30), (time(22), time(6)), _local(4, 22)),
    # window crossing midnight, due just after midnight: still inside, so last run + cadence
    (_local(4, 23, 10), _local(4, 23), (time(22), time(6)), _local(5, 0, 0, 5)),
    # the 00:00-00:00 default means all day
    (_local(4, 19, 31), _local(4, 19, 30), (time(0), time(0)), _local(4, 20, 30, 5)),
    # the check could not run (no credentials, another run in flight): a full cadence from now
    (_local(4, 10), None, (time(0), time(0)), _local(4, 11, 0, 5)),
    (_local(4, 12), _local(4, 9), (time(8), time(20)), _local(4, 13, 0, 5)),
])
def test_next_wake_at(now, last_run, window, expected):
    assert mailbox_loop.next_wake_at(now, last_run, 60, *window) == expected


@pytest.fixture
def clock(monkeypatch):
    state = {'now': _local(4, 12)}
    monkeypatch.setattr(timezone, 'now', lambda: state['now'])
    return state


@pytest.fixture
def owner_08_20(db, settings):
    settings.CODEX_CV_OWNER_EMAIL = 'owner@example.test'
    settings.GMAIL_OAUTH_CLIENT_ID, settings.GMAIL_OAUTH_CLIENT_SECRET = 'id', 'secret'  # run_check proceeds past its config gate
    owner = get_user_model().objects.create_user('owner', email='owner@example.test', password='pw')
    profile = user_profile_settings(owner)
    profile.mailbox_check_window_start, profile.mailbox_check_window_end = time(8), time(20)
    profile.save()
    return owner


def test_outside_the_window_the_loop_neither_queries_nor_writes_run_rows(owner_08_20, clock, monkeypatch):
    pipeline = []
    monkeypatch.setattr(mailbox_loop, 'daily_tick', lambda: pipeline.append(timezone.now()))
    request = queue_mailbox_check_request(owner_08_20)
    clock['now'] = _local(4, 21)  # the app starts in the evening: one schedule read, nothing else
    assert mailbox_loop.tick() == 3600
    assert mailbox_loop._next_wake == _local(5, 8)
    for hour in (22, 23):
        clock['now'] = _local(4, hour)
        with CaptureQueriesContext(connection) as queries:
            mailbox_loop.tick()
        assert len(queries) == 0
    assert MailboxRun.objects.count() == 0  # the real run_check would have written an outside_window row
    assert pipeline == []
    request.refresh_from_db()
    assert request.handled_at is None  # waits for the window to open


def test_inside_the_window_due_checks_run_at_cadence_and_nothing_in_between(owner_08_20, clock, monkeypatch):
    checks, pipeline = [], []

    def fake_run_check(force=False):  # the real cadence claim, without a Gmail transport
        run = mailbox._claim_run(timezone.now(), 60, force=force)
        mailbox._release_run()
        checks.append((timezone.localtime(timezone.now()).time(), force, run is not None))
        return run
    monkeypatch.setattr(mailbox, 'run_check', fake_run_check)
    monkeypatch.setattr(mailbox_loop, 'daily_tick', lambda: pipeline.append(timezone.now()))

    clock['now'] = _local(5, 8)
    mailbox_loop.tick()
    assert checks == [(time(8), False, True)] and len(pipeline) == 1
    assert mailbox_loop._next_wake == _local(5, 9, 0, 5)

    clock['now'] = _local(5, 8, 30)  # between due checks
    with CaptureQueriesContext(connection) as queries:
        assert mailbox_loop.tick() == 30 * 60 + 5
    assert len(queries) == 0

    request = queue_mailbox_check_request(owner_08_20)  # queued by the production site meanwhile
    clock['now'] = _local(5, 9, 0, 5)
    mailbox_loop.tick()
    request.refresh_from_db()
    assert request.handled_at is not None  # handled on the next wake, within one cadence
    assert checks[1:] == [(time(9, 0, 5), True, True)] and len(pipeline) == 2
    assert ScheduledTaskRun.objects.get(name=mailbox.TASK_NAME).last_run_at == _local(5, 9, 0, 5)
    assert mailbox_loop._next_wake == _local(5, 10, 0, 10)


def test_last_check_of_the_day_sleeps_until_the_window_opens(owner_08_20, clock, monkeypatch):
    monkeypatch.setattr(mailbox, 'run_check', lambda force=False: mailbox._claim_run(timezone.now(), 60))
    monkeypatch.setattr(mailbox_loop, 'daily_tick', lambda: None)
    clock['now'] = _local(5, 19, 30)
    mailbox_loop.tick()
    assert mailbox_loop._next_wake == _local(6, 8)  # not 20:30, which would only write an outside_window row


def test_a_failed_schedule_read_retries_soon_backs_off_and_resets(owner_08_20, clock, monkeypatch):
    """TASK-347: measured live, one PoolTimeout on the wake used to skip the mail check for an hour."""
    from django.db import OperationalError
    monkeypatch.setattr(mailbox, 'run_check', lambda force=False: mailbox._claim_run(timezone.now(), 60))
    monkeypatch.setattr(mailbox_loop, 'daily_tick', lambda: None)
    real_schedule = mailbox_loop._schedule

    def down():
        raise OperationalError("couldn't get a connection after 10.00 sec")
    monkeypatch.setattr(mailbox_loop, '_schedule', down)
    clock['now'] = _local(5, 9)
    sleeps = []
    for _ in range(8):
        seconds = mailbox_loop.tick()
        sleeps.append(seconds)
        clock['now'] += timedelta(seconds=seconds)
    assert sleeps == [60, 120, 240, 480, 960, 1920, 3600, 3600]

    monkeypatch.setattr(mailbox_loop, '_schedule', real_schedule)
    mailbox_loop.tick()  # the database is back: the check runs and the normal cadence resumes
    assert mailbox_loop._failures == 0
    assert mailbox_loop._next_wake == clock['now'] + timedelta(minutes=60, seconds=5)
    monkeypatch.setattr(mailbox_loop, '_schedule', down)
    clock['now'] = mailbox_loop._next_wake
    assert mailbox_loop.tick() == 60  # a later failure starts the backoff from the bottom again
