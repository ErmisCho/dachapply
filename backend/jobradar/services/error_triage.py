# TASK-372.2: deterministic local triage; the CLI is the only shared-task writer.
import json
import re
import shutil
import sqlite3
import subprocess
from contextlib import closing
from datetime import datetime, timezone  # TASK-372.3
from pathlib import Path

from . import error_occurrences as errors

ROOT = Path(__file__).resolve().parents[3]
DISPOSITIONS = {'cancelled': 'expected cancellation; no bug', 'quota': 'operator quota review; no bug',
                'transient': 'retry operational failure; no bug', 'unknown': 'manual review; cause unknown',
                'actionable': 'product bug', 'retry_exhausted': 'product bug; retries exhausted'}


def _cli(*args):
    result = subprocess.run([shutil.which('backlog') or 'backlog', *args], cwd=ROOT,
                            capture_output=True, text=True, timeout=60, check=True)
    return result.stdout


def _find(marker):
    tasks = json.loads(_cli('task', 'list', '--search', marker, '--json'))['tasks']
    matches = [t['id'] for t in tasks if marker in t['title']]
    if len(matches) > 1 or any(not re.fullmatch(r'TASK-\d+(?:\.\d+)*', t) for t in matches):
        raise ValueError('ambiguous task linkage')
    return matches[0] if matches else None


def triage(*, dry_run=False, list_only=False):
    """Only unresolved evidence participates. A write lock serializes concurrent triagers.

    Checkpoints commit after CLI success. A deterministic title marker recovers a task
    written by a CLI call that failed/was interrupted before its response was persisted.
    TASK-372.3: closure is explicit; Done alone never resolves local evidence.
    """
    with closing(errors._connect()) as db, db:
        db.row_factory = sqlite3.Row
        db.execute('BEGIN IMMEDIATE')
        groups = {}
        for row in db.execute('SELECT o.*, COALESCE(c.build, \'unknown\') AS build, COALESCE(c.classification, \'unknown\') AS classification FROM occurrences o LEFT JOIN occurrence_context c ON c.id=o.id WHERE o.resolved=0 ORDER BY o.at,o.id'):
            row = dict(row)
            signature = errors._digest(tuple(row[k] for k in ('source', 'environment', 'build', 'operation', 'error_type')))
            # TASK-372.3: new IDs always survive closure; successor markers recover interrupted creates.
            family = errors._digest(tuple(row[k] for k in ('source', 'environment', 'operation', 'error_type')))
            closure = db.execute('SELECT * FROM error_resolutions WHERE family=? ORDER BY rowid DESC LIMIT 1', (family,)).fetchone()
            if closure:
                row['recurrence'] = ('post-fix regression' if row['build'] != 'unknown' and row['build'] == closure['fixed_build']
                                     else 'unfixed or unknown runtime/build; regression unverified')
                if row['at'] <= closure['closed_at']:  # TASK-372.3: collection boundary, not replay time.
                    row['recurrence'] = 'pre-fix evidence; regression unverified'
                row['previous_task'] = closure['task_id']
                signature = errors._digest((signature, closure['signature'], row['recurrence']))
            linked = db.execute('SELECT signature FROM error_group_links WHERE occurrence_id=?', (row['id'],)).fetchone()
            if linked:  # TASK-372.3: another incident closing cannot move existing evidence.
                signature = linked['signature']
            groups.setdefault(signature, []).append(row)
        proposals = []
        for signature, rows in groups.items():
            checkpoint = errors._digest(json.dumps(rows, sort_keys=True))
            previous = db.execute('SELECT * FROM error_groups WHERE signature=?', (signature,)).fetchone()
            if not list_only and previous and previous['checkpoint'] == checkpoint:
                continue
            classes = {r['classification'] for r in rows}
            classification = next((c for c in ('retry_exhausted', 'actionable', 'unknown', 'transient', 'quota', 'cancelled') if c in classes), 'unknown')
            disposition = DISPOSITIONS[classification]
            if rows[0].get('recurrence'):  # TASK-372.3
                disposition += '; ' + rows[0]['recurrence'] + '; follows ' + rows[0]['previous_task']
            task_id = previous['task_id'] if previous else None
            actionable = classification in ('actionable', 'retry_exhausted')
            action = ('update' if task_id else 'create') if actionable else 'classify'
            proposal = dict(group=signature, task_id=task_id, count=len(rows), classification=classification,
                            disposition=disposition, action=action)
            proposals.append(proposal)
            if dry_run or list_only:
                continue
            if actionable:
                marker = 'error-group:' + signature
                task_id = task_id or _find(marker)
                # Only fixed vocabulary and digests enter shared files, even if local rows were edited.
                source = rows[0]['source'] if rows[0]['source'] in errors.SOURCES else 'backend'
                description = (f'{errors.SOURCES[source]}. Source: {source}. Environment/build/operation context: {signature}.\n'
                               f'Observed evidence: {len(rows)} unresolved failures; {disposition}.\n'
                               f'Environment: local. Build digest: {_token(rows[0]["build"])}. Affected operation digest: {_token(rows[0]["operation"])}.\n'
                               f'Collection time range (UTC): {_time(rows[0]["at"])} to {_time(rows[-1]["at"])}.\n'
                               'Reproduction steps: unknown. Root cause: unknown.\n'
                               'Private evidence is retained in the local occurrence store; ask its owner to inspect the group.')
                if not task_id:
                    _cli('task', 'create', f'{errors.SOURCES[source]} [{marker}]', '--type', 'bug',
                         '--description', description, '--ac', 'Reproduce or document why reproduction remains unknown using the linked local evidence.',
                         '--ac', 'Verify the affected operation succeeds and add a regression check for the confirmed cause.', '--plain')
                    task_id = _find(marker)
                    if not task_id:
                        raise ValueError('created task not found; retry to recover')
                else:
                    # review: never overwrite an investigator's description; append dated evidence instead
                    _cli('task', 'edit', task_id, '--append-notes', f'Error triage: {len(rows)} unresolved failures, last {_time(rows[-1]["at"])} UTC; {disposition}.')
                proposal['task_id'] = task_id
            db.execute('INSERT OR REPLACE INTO error_groups VALUES (?,?,?,?)', (signature, task_id, checkpoint, disposition))
            for row in rows:
                db.execute('INSERT OR REPLACE INTO error_group_links VALUES (?,?,?)', (row['id'], signature, row['evidence']))
        return proposals


def _token(value):
    return value if re.fullmatch(r'[a-f0-9]{64}', value) else 'unknown'


def _time(value):
    # Never publish arbitrary strings from a private store.
    from datetime import datetime
    try:
        return datetime.fromisoformat(value).isoformat()
    except (ValueError, TypeError):
        return 'unknown'


# TASK-372.3: caller attests completion with reviewable references, not a status-only claim.
def resolve(task_id, *, fix, tests, evaluation, merge, fixed_build):
    """References attest passing tests, PERFECT evaluation and the squash merge.

    Inspect linked IDs before external status I/O. New/unlinked arrivals are never closed.
    No CLI writes: interruption rolls back locally and retry is idempotent.
    """
    references = dict(fix=fix, tests=tests, evaluation=evaluation, merge=merge)
    if not re.fullmatch(r'TASK-\d+(?:\.\d+)*', task_id) or not fixed_build.strip() or any(not v.strip() for v in references.values()):
        raise ValueError('completion references and fixed build required')
    with closing(errors._connect()) as db, db:
        db.row_factory = sqlite3.Row
        db.execute('BEGIN IMMEDIATE')
        groups = db.execute('SELECT * FROM error_groups WHERE task_id=? AND signature NOT IN (SELECT signature FROM error_resolutions)', (task_id,)).fetchall()
        if not groups:
            return []
        task = json.loads(_cli('task', 'view', task_id, '--json'))['task']
        if task['id'] != task_id or task['status'] != 'Done' or task.get('type') != 'bug':
            raise ValueError('linked bug must be Done after verified completion')
        resolved = []
        for group in groups:
            rows = db.execute('SELECT o.* FROM occurrences o JOIN error_group_links l ON l.occurrence_id=o.id WHERE l.signature=? AND o.resolved=0', (group['signature'],)).fetchall()
            if not rows:
                continue
            family = errors._digest(tuple(rows[0][k] for k in ('source', 'environment', 'operation', 'error_type')))
            db.execute('INSERT INTO error_resolutions VALUES (?,?,?,?,?,?)',
                       (group['signature'], family, task_id, errors._digest(fixed_build), datetime.now(timezone.utc).isoformat(), json.dumps(references, sort_keys=True)))
            for row in rows:
                db.execute('UPDATE occurrences SET resolved=1 WHERE id=?', (row['id'],))
                resolved.append(row['id'])
        return resolved
