import logging
import os
import sys
import threading
import time
from datetime import datetime, time as dtime, timedelta

from django.conf import settings
from django.db import DatabaseError, IntegrityError, close_old_connections, transaction
from django.utils import timezone

from jobradar.models import ScheduledTaskRun
from jobradar.services.demo_data import ensure_demo_user

logger = logging.getLogger(__name__)

TASK_NAME = 'seed_demo_daily'
RUN_AT = dtime(4, 0)
_started = False
_started_lock = threading.Lock()


def _now_local():
    return timezone.localtime(timezone.now())


def _next_run_after(now):
    target = timezone.make_aware(datetime.combine(now.date(), RUN_AT), timezone.get_current_timezone())
    if now >= target:
        target += timedelta(days=1)
    return target


def seed_demo_if_due(force=False):
    """Refresh the public demo data once per local day at/after 04:00.

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


def _scheduler_loop():
    while True:
        seconds = 300
        try:
            close_old_connections()
            now = _now_local()
            if now.time() >= RUN_AT:
                seed_demo_if_due()
            next_run = _next_run_after(_now_local())
            seconds = max(60, min((next_run - _now_local()).total_seconds(), 3600))
        except DatabaseError as exc:
            logger.warning('Demo seed scheduler database unavailable: %s', exc)
        except Exception:
            logger.exception('Demo seed scheduler loop failed')
        finally:
            close_old_connections()
        time.sleep(seconds)


def _should_start_scheduler():
    if os.getenv('DACHAPPLY_DEMO_SEED_SCHEDULER', '1').strip().lower() in ('0', 'false', 'no', 'off'):
        return False
    command = os.path.basename(sys.argv[0]).lower()
    args = {arg.lower() for arg in sys.argv[1:]}
    skip = {'migrate', 'makemigrations', 'collectstatic', 'test', 'shell', 'dbshell', 'seed_demo'}
    if command.endswith('pytest') or any('pytest' in arg for arg in [command, *args]) or args & skip:
        return False
    if command in ('manage.py', 'django-admin') and 'runserver' not in args:
        return False
    if settings.DEBUG and os.environ.get('RUN_MAIN') != 'true' and 'runserver' in args:
        return False
    return True


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
