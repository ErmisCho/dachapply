"""TASK-406.4: one supervised agent run that turns a group of failed documents into a pull request.

A run is a dict: id, signature, state ('running', 'pr', 'merged', 'failed', 'stopped', 'interrupted'),
step, started_at, finished_at (ISO or ''), log (last lines, a list), pr_url, task_id, error.
"""


def status():
    """{'enabled': bool, 'reason': why Fix is off or ''}. The page shows the reason."""
    return {'enabled': False, 'reason': 'Fix runs are not built yet.'}


def runs():
    """Every run, newest first."""
    return []


def start(signature, user):
    """Start the one run for this group and return it. Raises ValueError with a message for the owner."""
    raise ValueError(status()['reason'])


def stop(run_id):
    """Stop a running run and return it. Raises ValueError."""
    raise ValueError('That run is not running.')
