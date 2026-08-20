"""TASK-124 AC1/AC2: the manual "run now" trigger for the mailbox check.

Same daemon-Thread + in-memory registry shape as cv_tasks.py (start_cv_task/get_cv_task) -- that
module's own docstring/task notes call out its limitation: the registry dies with the process, which
is fine here too, since a check started on a machine that is watching it lives and dies with that
same process. That is exactly why AC2 does NOT use this registry at all on a backend with no mail
credentials (the deployed site) -- there, services.mailbox.queue_mailbox_check_request() writes a
real MailboxCheckRequest row instead, for the owner's own machine to pick up later, possibly long
after this process (and any in-memory task) is gone.
"""
import time
import uuid
from threading import Lock, Thread

from django.db import close_old_connections

from jobradar.services.mailbox import (
    MailboxCheckInProgress,
    has_mailbox_credentials,
    queue_mailbox_check_request,
    run_check,
)

_tasks = {}
_lock = Lock()


def _cleanup():
    cutoff = time.time() - 3600
    with _lock:
        for task_id in [key for key, task in _tasks.items() if task['updated_at'] < cutoff]:
            del _tasks[task_id]


def _update(task_id, **values):
    with _lock:
        task = _tasks.get(task_id)
        if task is None:
            return
        task.update(values, updated_at=time.time())


def _run(task_id):
    close_old_connections()
    try:
        run = run_check(force=True)
    except MailboxCheckInProgress as exc:
        # AC4: told, not silently dropped -- a poller reading this task sees status='refused' rather
        # than a run that looks like it just never started.
        _update(task_id, status='refused', error=str(exc))
        return
    except Exception as exc:
        _update(task_id, status='failed', error=str(exc)[:500])
        return
    finally:
        close_old_connections()
    if run is None:
        # has_mailbox_credentials() already rules out "not configured" before this thread is ever
        # started (see start_mailbox_check), so in practice this is only reachable if
        # CODEX_CV_OWNER_EMAIL matches no user account.
        _update(task_id, status='failed', error='Mailbox check did not run: no owner account is configured for this backend.')
    elif run.error:
        _update(task_id, status='failed', error=run.error, run_id=run.id)
    else:
        _update(task_id, status='done', run_id=run.id, skipped=run.skipped, skip_reason=run.skip_reason)


def start_mailbox_check(user) -> dict:
    """AC1/AC2: on a backend WITH credentials, starts run_check() on a daemon thread and returns a
    handle immediately -- callers poll get_mailbox_check_task(task_id, user_id) rather than waiting on
    this call, since a real run can take long enough to matter (TASK-109's first live run: 641
    messages). WITHOUT credentials, records a MailboxCheckRequest instead (AC2) and returns that
    request's id so the caller can say plainly that nothing has started yet.

    AC8/AC5 (TASK-125): whether checking is currently disabled or outside its window is NOT decided
    here -- run_check() itself still applies those gates (in the same order as every other trigger)
    and records the outcome on the MailboxRun the task ends up pointing at, so a manual run gets the
    same honest refusal a scheduled one would, not a bypass.
    """
    _cleanup()
    if not has_mailbox_credentials():
        request = queue_mailbox_check_request(user)
        return {'queued': True, 'request_id': request.id}
    task_id = uuid.uuid4().hex
    with _lock:
        _tasks[task_id] = {
            'id': task_id, 'user_id': user.id, 'status': 'running', 'run_id': None,
            'error': '', 'skipped': False, 'skip_reason': '', 'updated_at': time.time(),
        }
    Thread(target=_run, args=(task_id,), name=f'mailbox-check-{task_id[:8]}', daemon=True).start()
    return {'queued': False, 'task_id': task_id}


def get_mailbox_check_task(task_id, user_id) -> dict | None:
    """Scoped to the user who started it, same shape/contract as cv_tasks.get_cv_task."""
    _cleanup()
    with _lock:
        task = _tasks.get(task_id)
        if not task or task['user_id'] != user_id:
            return None
        return {key: value for key, value in task.items() if key not in ('user_id', 'updated_at')}
