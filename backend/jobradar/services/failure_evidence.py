"""TASK-406.1/406.2: private local evidence of every failed document, and the cause it is grouped by.

Records live in <workspace>/.dachapply-logs/failures/<record id>.json; the files they name (failed TeX,
LaTeX logs, rejected model answers) in .dachapply-logs/failed/. Both hold CV and letter text: never put
them in git, Backlog, an export or a response to another account.
"""
import hashlib
import json
import logging
import re
import time
from datetime import datetime
from pathlib import Path

from django.conf import settings

logger = logging.getLogger(__name__)
KEEP_DAYS = 30
# First match wins. Only a cause listed as actionable files a bug; anything unrecognised waits for a manual look.
CLASSES = (
    ('quota', r'usage limit|rate limit|limit reached'),
    ('transient', r'server closed the connection|consuming input failed|connection (?:refused|reset|timed out)|WinError 32|being used by another process|is open in another program|database is locked|could not complete the request'),
    ('cancelled', r'\bcancelled\b'),
    ('unknown', r'exceeds its \S+ limit'),
    ('actionable', r'LaTeX could not compile|returned invalid|could not verify the page count'),
)


def logs_dir():
    # DEBUG is the local runtime, as for error_occurrences: a deployment never keeps these files.
    workspace = getattr(settings, 'CODEX_CV_WORKSPACE', '') or ''
    return Path(workspace)/'.dachapply-logs' if settings.DEBUG and workspace and Path(workspace).is_dir() else None  # never create the workspace itself


def _private(folder, name):
    (folder/name).mkdir(parents=True, exist_ok=True)
    (folder/'.gitignore').write_text('*', encoding='utf-8')  # the workspace may be somebody's checkout
    return folder/name


def classify(error):
    return next((name for name, pattern in CLASSES if re.search(pattern, error or '', re.IGNORECASE)), 'unknown')


def cause(error, diagnostics=''):
    """One line naming what went wrong, without the job, names, numbers or text that vary per failure."""
    line = (str(error or '').strip().splitlines() or ['Unknown error'])[0]
    if 'invalid application documents' in line:  # the rejected answer's own problem says which kind of invalid
        problem = re.search(r'^Attempt 1: .*\n(.+)', str(diagnostics or ''))
        line = 'Invalid document: ' + (problem[1] if problem else 'no reason recorded')
        line = re.split(r';|: ?[\'"]', line.replace('cv_tex', 'the document').replace('letter_tex', 'the document'))[0]
    line = re.sub(r'\s*(?:Two automatic repair attempts also failed\.?)', '', line)
    line = re.sub(r'the (?:CV|motivation letter)\b', 'the document', line, flags=re.IGNORECASE)
    line = re.sub(r'\(?[A-Za-z]:\\[^\s\'"]+|\S+\.(?:tex|pdf|log)\b', '<file>', line)
    line = re.sub(r'character .{1,4} \(U\+[0-9A-F]+\)', 'character (U+N)', line)
    line = re.sub(r'\'[^\']*\'|"[^"]*"', '<text>', line)
    line = re.sub(r'\d+', 'N', line)
    return re.sub(r'\s+', ' ', line).strip(' .')[:200]


def signature(error, diagnostics=''):
    return hashlib.sha256(cause(error, diagnostics).casefold().encode()).hexdigest()


def prune():
    """Run by the local loop at least hourly, so old evidence goes even when nothing fails any more."""
    try:
        folder, limit = logs_dir(), time.time() - KEEP_DAYS*86400
        for path in [*(folder/'failures').glob('*.json'), *(folder/'failed').glob('*')] if folder else ():
            if path.is_file() and path.stat().st_mtime < limit:
                path.unlink(missing_ok=True)
    except OSError:
        logger.debug('Could not prune old failure evidence', exc_info=True)


def record(task):
    """One JSON per failed task. Never raises: saving evidence must not change a task's result."""
    try:
        folder = logs_dir()
        if not folder:
            return
        target = _private(folder, 'failures')
        config = task.get('_config') or {}
        adjust = task.get('_adjust') or {}
        error, diagnostics = str(task.get('error') or ''), str(task.get('diagnostics') or '')
        data = {'id': task['id'], 'time': datetime.now().astimezone().isoformat(timespec='seconds'), 'job_id': task.get('job_id'), 'user_id': task.get('user_id'),
                'route': adjust.get('route') or 'generation-or-recompile', 'provider': config.get('provider', ''), 'model': config.get('model', ''), 'effort': config.get('effort', ''),
                'error': error[:500], 'diagnostics': diagnostics[:20000], 'instructions': str(adjust.get('instructions') or '')[:5000],
                'cause': cause(error, diagnostics), 'signature': signature(error, diagnostics), 'class': classify(error),
                'files': [str(path) for path in task.get('_failed_files', [])]}
        (target/f'{task["id"]}.json').write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding='utf-8')
    except Exception:
        logger.debug('Could not record the failure of task %s', task.get('id'), exc_info=True)


def save_answer(name, text):
    """The model answer a validation rejected, whole. Returns the saved paths; never raises."""
    try:
        folder = logs_dir()
        if not folder or not text:
            return []
        target = _private(folder, 'failed')/f'{time.strftime("%Y%m%d-%H%M%S")}-{time.time_ns() % 10**6:06d}-rejected-{Path(name).stem}.tex'
        target.write_text(text, encoding='utf-8')
        return [str(target)]
    except Exception:
        logger.debug('Could not save the rejected answer for %s', name, exc_info=True)
        return []


def records(user_id):
    """This account's records, newest first. A file that cannot be read is left out."""
    folder = logs_dir()
    rows = []
    for path in (folder/'failures').glob('*.json') if folder else ():
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            continue
        if data.get('user_id') == user_id:
            rows.append(data)
    return sorted(rows, key=lambda row: row['time'], reverse=True)
