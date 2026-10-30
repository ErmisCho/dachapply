import logging
import os
import sys
import threading
import time
from datetime import datetime, time as dtime, timedelta

from django.db import DatabaseError, IntegrityError, close_old_connections, transaction
from django.utils import timezone

from jobradar.models import ScheduledTaskRun
from jobradar.services.demo_data import ensure_demo_user
from jobradar.services.followup_digest import send_due_digests

logger = logging.getLogger(__name__)

TASK_NAME = 'seed_demo_daily'
# TASK-347: 08:00-20:00 local, the owner's Neon window (was 04:00 then an hourly DB poll all day).
RUN_AT = dtime(8, 0)
RUN_UNTIL = dtime(20, 0)
MAX_SLEEP_SECONDS = 3600  # only bounds a suspended laptop or DST; a wake that has nothing due is DB-free
RETRY_SECONDS = 60  # a database error retries after 60, 120, 240 s ... capped at MAX_SLEEP_SECONDS
_done_on = None  # in-process: the local date this loop last ran its daily work
_failures = 0  # consecutive database errors
_started = False
_started_lock = threading.Lock()


def _now_local():
    return timezone.localtime(timezone.now())


def _next_window_start(now):
    """Today's RUN_AT if it is still ahead and today's work is not done, else tomorrow's."""
    day = now.date() if now.time() < RUN_AT and _done_on != now.date() else now.date() + timedelta(days=1)
    return timezone.make_aware(datetime.combine(day, RUN_AT), timezone.get_current_timezone())


def seed_demo_if_due(force=False):
    """Refresh the public demo data once per local day at/after RUN_AT.

    Returns (ran, demo_user, jobs). `force=True` is used by the admin button and
    management command-like manual paths.
    """
    now = _now_local()
    if not force and now.time() < RUN_AT:
        return False, None, []

    try:
        close_old_connections()
        with transaction.atomic():
            try:
                task, _ = ScheduledTaskRun.objects.select_for_update().get_or_create(name=TASK_NAME)
            except IntegrityError:
                task = ScheduledTaskRun.objects.select_for_update().get(name=TASK_NAME)
            last = timezone.localtime(task.last_run_at) if task.last_run_at else None
            if not force and last and last.date() == now.date():
                return False, None, []
            # Claim today's run before doing the heavier reset so multiple web
            # workers do not seed concurrently.
            task.last_run_at = timezone.now()
            task.save(update_fields=['last_run_at', 'updated_at'])
    except DatabaseError as exc:
        logger.warning('Could not claim demo seed task: %s', exc)
        close_old_connections()
        return False, None, []
    except Exception:
        logger.exception('Could not claim demo seed task')
        close_old_connections()
        return False, None, []

    user, jobs = ensure_demo_user()
    return True, user, jobs


def scheduler_tick():
    """One wake; returns the seconds to sleep. TASK-347: touches the database only when today's work is
    not done yet and the local time is inside RUN_AT-RUN_UNTIL -- at most once per local day."""
    global _done_on, _failures
    now = _now_local()
    if _done_on != now.date() and RUN_AT <= now.time() < RUN_UNTIL:
        try:
            close_old_connections()
            seed_demo_if_due()
            # Second task on the same daily tick; it keeps its own ScheduledTaskRun day guard, so a
            # restarted process (fresh _done_on) still never double-sends.
            send_due_digests()
            _done_on, _failures = now.date(), 0
        except DatabaseError as exc:
            logger.warning('Demo seed scheduler database unavailable: %s', exc)
            _failures += 1
            return min(RETRY_SECONDS * 2 ** (_failures - 1), MAX_SLEEP_SECONDS)  # retried inside the window only
        except Exception:
            logger.exception('Demo seed scheduler loop failed')
            return MAX_SLEEP_SECONDS
        finally:
            close_old_connections()
    return max(60, min((_next_window_start(now) - now).total_seconds(), MAX_SLEEP_SECONDS))


def _scheduler_loop():
    while True:
        time.sleep(scheduler_tick())


def should_start_local_loop(env_var):
    """TASK-276: in-process loops run only while the owner runs the app locally (`manage.py runserver`),
    never under gunicorn (Azure), pytest, or any other management command. `env_var`=0 disables one."""
    if os.getenv(env_var, '1').strip().lower() in ('0', 'false', 'no', 'off'):
        return False
    # TASK-273: `python -m pytest` has argv[0] == '__main__.py', so argv alone misses it and the
    # scheduler seeded demo mail into the test database mid-run. A loaded pytest is the real signal.
    if 'pytest' in sys.modules:
        return False
    args = {arg.lower() for arg in sys.argv[1:]}
    if 'runserver' not in args:
        return False
    # The autoreloader parent (no RUN_MAIN) only watches files -- whatever DEBUG says, runserver
    # reloads unless --noreload -- so start once, in the serving child.
    return '--noreload' in args or os.environ.get('RUN_MAIN') == 'true'


def _should_start_scheduler():
    return should_start_local_loop('DACHAPPLY_DEMO_SEED_SCHEDULER')


def start_demo_seed_scheduler():
    global _started
    if not _should_start_scheduler():
        return False
    with _started_lock:
        if _started:
            return False
        _started = True
        thread = threading.Thread(target=_scheduler_loop, name='dachapply-demo-seed-scheduler', daemon=True)
        thread.start()
        return True
