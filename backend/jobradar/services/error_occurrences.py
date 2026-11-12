"""TASK-372.1: opt-in LOCAL collection; never retain messages, tracebacks or payloads."""
import hashlib
import logging
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from django.conf import settings

SOURCES = {
    'backend': 'Backend operation failed',
    'pipeline': 'Application preparation failed',
    'document': 'Document generation failed',
    'provider': 'Provider operation failed',
    'compile': 'Document compilation failed',
    'mailbox': 'Mailbox check failed',
}
MAX_ROWS = 10000
MAX_BATCH = 100
_health = 'disabled'


def health():
    """Safe process-local signal; no exception strings or paths."""
    return _health


def _digest(value):
    return hashlib.sha256(str(value).encode()).hexdigest()


def _connect():
    # The owner provisions an owner-only directory OUTSIDE the checkout (ACLs on Windows).
    path = Path(settings.ERROR_OCCURRENCE_LOCAL_DB).resolve()
    if not settings.DEBUG or path.is_relative_to(Path(settings.BASE_DIR).parent.resolve()):
        raise ValueError('local store only, outside checkout')
    if not path.parent.is_dir():
        raise ValueError('provision private directory first')
    db = sqlite3.connect(path, timeout=0.2)
    try:
        db.execute('PRAGMA max_page_count=4096')  # 16 MiB at SQLite's default page size
        db.execute('CREATE TABLE IF NOT EXISTS occurrences (id TEXT PRIMARY KEY, at TEXT NOT NULL, source TEXT NOT NULL, environment TEXT NOT NULL, operation TEXT NOT NULL, error_type TEXT NOT NULL, summary TEXT NOT NULL, evidence TEXT NOT NULL, resolved INTEGER NOT NULL DEFAULT 0)')
        db.execute('CREATE TABLE IF NOT EXISTS intake (source TEXT PRIMARY KEY, cursor TEXT NOT NULL)')
    except Exception:
        db.close()
        raise
    return db


def ingest(source, events, *, cursor=None):
    """Atomic bounded batch. Producer supplies stable event ids, distinct for separate failures.

    Cursor is an opaque source generation/offset token, hashed before storage. Neither source
    files nor payloads are retained. Replay keys and progress commit together, including warnings.
    """
    global _health
    if not getattr(settings, 'ERROR_OCCURRENCE_LOCAL_DB', ''):
        _health = 'disabled'
        return []
    try:
        if source not in SOURCES:
            raise ValueError('unknown source')
        with closing(_connect()) as db, db:
            db.execute('BEGIN IMMEDIATE')
            ids = []
            for index, event in enumerate(events):
                if index >= MAX_BATCH:
                    raise ValueError('batch too large')
                if event.get('status') != 'failed':
                    continue
                event_id = str(uuid.uuid5(uuid.NAMESPACE_URL, source + ':' + _digest(event['id'])))
                if db.execute('SELECT 1 FROM occurrences WHERE id=?', (event_id,)).fetchone():
                    ids.append(event_id)
                    continue
                if db.execute('SELECT count(*) FROM occurrences').fetchone()[0] >= MAX_ROWS:
                    raise ValueError('store full')
                at = datetime.now(timezone.utc).isoformat()
                # Fixed vocabulary is safer than attempting to redact arbitrary provider/CV text.
                db.execute('INSERT INTO occurrences VALUES (?,?,?,?,?,?,?,?,0)',
                           (event_id, at, source, 'local', _digest(event.get('operation', event['id'])),
                            'OperationFailed', SOURCES[source], 'occurrence:' + event_id))
                ids.append(event_id)
            if cursor is not None:
                db.execute('INSERT OR REPLACE INTO intake VALUES (?,?)', (source, _digest(cursor)))
        _health = 'ok'
        return ids
    except Exception:
        # Never log collector failures: ERROR handlers would recurse and may expose private data.
        _health = 'degraded'
        return []


def capture(source, identity=None, operation=None):
    return ingest(source, [{'id': identity if identity is not None else uuid.uuid4().hex,
                            'operation': operation, 'status': 'failed'}])


def unresolved(limit=100):
    """Safe query seam for TASK-372.2/372.3; no public endpoint or resolution implementation."""
    global _health
    try:
        with closing(_connect()) as db:
            db.row_factory = sqlite3.Row
            return [dict(row) for row in db.execute('SELECT * FROM occurrences WHERE resolved=0 ORDER BY at,id LIMIT ?', (max(0, min(limit, MAX_BATCH)),))]
    except Exception:
        _health = 'degraded'
        return []


def progress(source):
    """Last committed cursor digest; compare with sha256 of a producer generation/offset token."""
    global _health
    try:
        with closing(_connect()) as db:
            row = db.execute('SELECT cursor FROM intake WHERE source=?', (source,)).fetchone()
            return row[0] if row else None
    except Exception:
        _health = 'degraded'
        return None


class OccurrenceHandler(logging.Handler):
    def emit(self, record):
        if record.levelno >= logging.ERROR:
            capture('backend', operation=record.name)  # Never format msg, args, request or exc_info.
