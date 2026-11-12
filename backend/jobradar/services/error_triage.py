# TASK-372.2: deterministic local triage; the CLI is the only shared-task writer.
import json
import re
import shutil
import sqlite3
import subprocess
from contextlib import closing
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
    Existing links are retained even if someone closes a task; resolution is TASK-372.3.
    """
    with closing(errors._connect()) as db, db:
        db.row_factory = sqlite3.Row
        db.execute('BEGIN IMMEDIATE')
        groups = {}
        for row in db.execute('SELECT o.*, COALESCE(c.build, \'unknown\') AS build, COALESCE(c.classification, \'unknown\') AS classification FROM occurrences o LEFT JOIN occurrence_context c ON c.id=o.id WHERE o.resolved=0 ORDER BY o.at,o.id'):
            row = dict(row)
            signature = errors._digest(tuple(row[k] for k in ('source', 'environment', 'build', 'operation', 'error_type')))
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
                    _cli('task', 'edit', task_id, '--description', description)
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
