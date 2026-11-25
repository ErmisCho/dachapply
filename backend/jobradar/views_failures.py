"""TASK-406.3: the owner's failure groups, their records and the supervised fix runs. Own module, like views_application_prep.py."""
from pathlib import Path

from rest_framework.decorators import api_view, throttle_classes
from rest_framework.response import Response

from .services import failure_evidence, fix_runs
from .services.cv_generator import is_env_cv_owner
from .throttles import CVGenerationUserThrottle

MAX_TEXT = 200_000


def _allowed(user):
    return is_env_cv_owner(user) and failure_evidence.logs_dir() is not None


def _not_found():
    return Response({'detail': 'Not found.'}, status=404)


def _local(request):
    """The app is reachable over Tailscale through a proxy on 127.0.0.1, so the address alone proves nothing."""
    headers = [key for key in request.META if key.startswith(('HTTP_X_FORWARDED_', 'HTTP_TAILSCALE_'))]
    return (request.META.get('REMOTE_ADDR') in ('127.0.0.1', '::1') and request.get_host().rsplit(':', 1)[0].strip('[]') in ('localhost', '127.0.0.1', '::1')
            and not headers)


def _file(path, root):
    """The JSON's paths are data, not trusted: only a file that resolves inside logs/failed is read."""
    name = Path(str(path)).name
    try:
        target = Path(str(path)).resolve()
        if not target.is_relative_to(root.resolve()) or not target.is_file():
            return {'name': name, 'text': None}
        with target.open('rb') as handle:
            return {'name': name, 'text': handle.read(MAX_TEXT).decode('utf-8', errors='replace')}
    except (OSError, ValueError):
        return {'name': name, 'text': None}


@api_view(['GET'])
def failure_groups(request):
    if not _allowed(request.user):
        return _not_found()
    newest = {}
    for run in fix_runs.runs():  # newest first
        newest.setdefault(run.get('signature'), run)
    groups = {}
    for row in failure_evidence.records(request.user.id):  # newest first
        group = groups.setdefault(row['signature'], {'signature': row['signature'], 'cause': row['cause'], 'class': row['class'], 'count': 0, 'last': row['time'], 'job_ids': []})
        group['count'] += 1
        if row.get('job_id') not in group['job_ids']:
            group['job_ids'].append(row.get('job_id'))
    for group in groups.values():
        run = newest.get(group['signature'])
        if run and run.get('state') not in ('running', 'pr', 'merged'):
            run = {**run, 'task_id': ''}  # TASK-413: its task file went with the worktree (also runs saved before the fix)
        group['run'], group['task_id'] = run, (run or {}).get('task_id') or ''
        group['state'] = run['state'] if run else {'actionable': 'new', 'unknown': 'look'}.get(group['class'], 'not_a_bug')
    return Response({'groups': list(groups.values()), 'fix': fix_runs.status()})


@api_view(['GET'])
def failure_group(request, signature):
    if not _allowed(request.user):
        return _not_found()
    root = failure_evidence.logs_dir()/'failed'
    rows = [{**row, 'files': [_file(path, root) for path in row.get('files') or []]} for row in failure_evidence.records(request.user.id) if row['signature'] == signature]
    return Response({'records': rows})


@api_view(['POST'])
@throttle_classes([CVGenerationUserThrottle])
def failure_fix(request, signature):
    if not _allowed(request.user):
        return _not_found()
    if not _local(request):
        return Response({'detail': 'Fix can only be started from the computer the app runs on, not over Tailscale or a proxy.'}, status=403)
    try:
        return Response(fix_runs.start(signature, request.user), status=202)
    except ValueError as exc:
        return Response({'detail': str(exc)}, status=400)


@api_view(['POST'])
@throttle_classes([CVGenerationUserThrottle])
def failure_run_stop(request, run_id):
    if not _allowed(request.user):
        return _not_found()
    try:
        return Response(fix_runs.stop(run_id))
    except ValueError as exc:
        return Response({'detail': str(exc)}, status=400)
