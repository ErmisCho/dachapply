"""TASK-276: the hourly mailbox check runs inside the local app, only while the owner runs it.

Replaces TASK-275's Windows scheduled task. Every TICK_SECONDS it runs the check_mailbox command's
tick with force=False, so UserProfile cadence, check window and calendar quiet hours decide when a
check really happens; a pending manual request still runs first. Same daemon-thread shape and start
gate as demo_scheduler (runserver only). Disable with DACHAPPLY_LOCAL_MAILBOX_LOOP=0.
"""
import logging
import threading
import time

from django.db import close_old_connections

from jobradar.services.demo_scheduler import should_start_local_loop
from jobradar.services.mailbox import MailboxCheckInProgress, check_mailbox_tick

logger = logging.getLogger(__name__)

TICK_SECONDS = 300
_started = False
_started_lock = threading.Lock()


def tick():
    """One iteration; never raises, so a bad tick cannot kill the thread or runserver."""
    try:
        close_old_connections()
        check_mailbox_tick(force=False)
    except MailboxCheckInProgress:
        pass  # another run (manual button, a terminal) is in flight; the next tick catches up
    except Exception:
        logger.exception('Local mailbox loop tick failed')
    finally:
        close_old_connections()


def _loop():
    while True:
        tick()
        time.sleep(TICK_SECONDS)


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
