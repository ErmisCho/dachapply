"""TASK-276: the hourly mailbox check runs inside the local app, only while the owner runs it.

Replaces TASK-275's Windows scheduled task. Each wake runs the check_mailbox command's tick with
force=False, so UserProfile cadence, check window and calendar quiet hours decide when a check really
happens; a pending manual request still runs first. Same daemon-thread shape and start gate as
demo_scheduler (runserver only). Disable with DACHAPPLY_LOCAL_MAILBOX_LOOP=0.
TASK-335..337: each wake first spends the daily pipeline budgets (application_prep.daily_tick).
TASK-347: the loop used to wake every 300 s -- exactly Neon's scale-to-zero window, so the compute never
suspended while the app ran and the free-plan quota ran out. It now sleeps until the next check is due
(last run + cadence, moved into the profile's check window) and a wake before that touches no database.
"""
import logging
import threading
import time
from datetime import datetime, timedelta

from django.db import close_old_connections
from django.utils import timezone

from jobradar.models import ScheduledTaskRun
from jobradar.services import mailbox
from jobradar.services.application_prep import daily_tick
from jobradar.services.demo_scheduler import should_start_local_loop
from jobradar.services.mailbox import MailboxCheckInProgress, check_mailbox_tick, is_within_check_window
from jobradar.services.prompt_builder import user_profile_settings

logger = logging.getLogger(__name__)

# TASK-347: the longest single sleep. A wake before _next_wake is DB-free, so this only bounds how
# late a suspended laptop or a DST change can leave the loop; no owner/profile also waits this long.
MAX_SLEEP_SECONDS = 3600
# Past the due moment, so _claim_run's `now - last_run_at < cadence` gate has certainly elapsed.
SLACK = timedelta(seconds=5)
# TASK-347: a wake whose schedule read fails retries after 60, 120, 240 s ... capped at MAX_SLEEP_SECONDS,
# reset by the next good read -- measured 2026-10-30, one PoolTimeout otherwise cost the check an hour,
# and a refusing database (Neon quota exceeded) is still only asked a handful of times an hour.
RETRY_SECONDS = 60
_next_wake = None  # in-process only: when the next DB-touching wake is due; None until the first wake
_failures = 0  # consecutive failed schedule reads
_started = False
_started_lock = threading.Lock()


def window_opens_after(moment, start):
    """The first local `start` time strictly after `moment` (aware)."""
    local = timezone.localtime(moment)
    opens = timezone.make_aware(datetime.combine(local.date(), start))
    return opens if opens > local else timezone.make_aware(datetime.combine(local.date() + timedelta(days=1), start))


def next_wake_at(now, last_run_at, cadence_minutes, start, end):
    """Pure: when the loop next needs the database. Last run + cadence (or a full cadence from now when
    that has already passed -- the check just could not run: no credentials, another run in flight),
    then moved to the window's next opening if it falls outside [start, end] (start == end: all day)."""
    cadence = timedelta(minutes=cadence_minutes)
    due = (last_run_at + cadence if last_run_at and last_run_at + cadence > now else now + cadence) + SLACK
    return due if is_within_check_window(timezone.localtime(due).time(), start, end) else window_opens_after(due, start)


def _schedule():
    """(last_run_at, cadence, window_start, window_end) for the owner, or None with no owner account."""
    owner = mailbox._owner_user()
    if owner is None:
        return None
    profile = user_profile_settings(owner)
    task = ScheduledTaskRun.objects.filter(name=mailbox.TASK_NAME).first()
    return (task.last_run_at if task else None, profile.mailbox_check_cadence_minutes or 60,
            profile.mailbox_check_window_start, profile.mailbox_check_window_end)


def _retry_soon(now):
    global _next_wake, _failures
    logger.exception('Local mailbox loop could not read the check schedule')
    _failures += 1
    _next_wake = now + timedelta(seconds=min(RETRY_SECONDS * 2 ** (_failures - 1), MAX_SLEEP_SECONDS))


def _sleep_seconds(now):
    return max(1.0, min((_next_wake - now).total_seconds(), MAX_SLEEP_SECONDS))


def tick():
    """One wake; returns the seconds to sleep. Never raises, so a bad wake cannot kill the thread or
    runserver. Before _next_wake it returns without any database access (TASK-347 AC1/AC2)."""
    global _next_wake, _failures
    now = timezone.now()
    if _next_wake is not None and now < _next_wake - SLACK:
        return _sleep_seconds(now)
    try:
        close_old_connections()
        schedule = _schedule()
        _failures = 0
        # First wake outside the window (the app started in the evening): only the profile was read,
        # no run row and no pipeline -- both wait for the window to open.
        if schedule and not is_within_check_window(timezone.localtime(now).time(), schedule[2], schedule[3]):
            _next_wake = window_opens_after(now, schedule[2])
            return _sleep_seconds(now)
    except Exception:
        _retry_soon(now)
        close_old_connections()
        return _sleep_seconds(now)
    try:
        close_old_connections()
        # TASK-335..337: the daily pipeline budgets ride this loop (local app only); quick, it only starts threads.
        daily_tick()
    except Exception:
        logger.exception('Daily pipeline run failed')
    try:
        close_old_connections()
        check_mailbox_tick(force=False)
    except MailboxCheckInProgress:
        pass  # another run (manual button, a terminal) is in flight; the next wake catches up
    except Exception:
        logger.exception('Local mailbox loop tick failed')
    try:
        schedule = _schedule()
        _failures = 0
        _next_wake = next_wake_at(timezone.now(), *schedule) if schedule else now + timedelta(seconds=MAX_SLEEP_SECONDS)
    except Exception:
        _retry_soon(timezone.now())
    finally:
        close_old_connections()
    return _sleep_seconds(timezone.now())


def _loop():
    while True:
        time.sleep(tick())


def start_local_mailbox_loop():
    global _started
    if not should_start_local_loop('DACHAPPLY_LOCAL_MAILBOX_LOOP'):
        return False
    with _started_lock:
        if _started:
            return False
        _started = True
        threading.Thread(target=_loop, name='dachapply-local-mailbox-loop', daemon=True).start()
        return True
