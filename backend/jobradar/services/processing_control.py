"""Local supervisor's cooperative gate. Never suspend a process or interrupt a safe unit."""
import functools
import base64
import inspect
import json
import logging
import os
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager

_local = threading.local()
_handlers = {}


def event(name, kind='runtime'):
    logging.getLogger('dashboard.events').info(json.dumps({
        'time': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'event': name, 'kind': kind}))


class Store:
    def __init__(self, path):
        self.path = str(path)
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS control (id INTEGER PRIMARY KEY, mode TEXT NOT NULL);
                INSERT OR IGNORE INTO control VALUES (1, 'running');
                CREATE TABLE IF NOT EXISTS units (
                    id TEXT PRIMARY KEY, kind TEXT NOT NULL, payload TEXT NOT NULL,
                    state TEXT NOT NULL, created REAL NOT NULL);
                CREATE UNIQUE INDEX IF NOT EXISTS pending_unit ON units(kind, payload)
                    WHERE state IN ('queued', 'running');
            ''')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.execute('PRAGMA busy_timeout=15000')
        try:
            with db:
                yield db
        finally:
            db.close()

    def mode(self, value=None):
        with self.connect() as db:
            if value is not None:
                if value not in ('running', 'paused', 'stopping'):
                    raise ValueError('Invalid processing mode')
                db.execute('UPDATE control SET mode=? WHERE id=1', (value,))
            return db.execute('SELECT mode FROM control WHERE id=1').fetchone()[0]

    def enqueue(self, kind, payload):
        identity = json.dumps(payload, sort_keys=True, separators=(',', ':'))
        unit_id = uuid.uuid4().hex
        with self.connect() as db:
            cursor = db.execute('INSERT OR IGNORE INTO units VALUES (?, ?, ?, ?, ?)',
                                (unit_id, kind, identity, 'queued', time.time()))
            return unit_id if cursor.rowcount else None

    def claim(self, unit_id, kind, limit):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT mode FROM control WHERE id=1').fetchone()[0] != 'running':
                return False
            # These workers share application_prep._pipeline_lock. A waiting worker is queued,
            # so Pause must prevent it becoming the next safe unit after that lock is released.
            if kind in ('pipeline', 'daily-document'):
                active = db.execute("SELECT count(*) FROM units WHERE kind IN ('pipeline','daily-document') AND state='running'").fetchone()[0]
            else:
                active = db.execute("SELECT count(*) FROM units WHERE kind=? AND state='running'", (kind,)).fetchone()[0]
            if active >= limit:
                return False
            return bool(db.execute("UPDATE units SET state='running' WHERE id=? AND state='queued'", (unit_id,)).rowcount)

    def finish(self, unit_id, state='completed'):
        with self.connect() as db:
            db.execute("UPDATE units SET state=?, payload=CASE WHEN ? IN ('completed','failed') THEN '{}' ELSE payload END WHERE id=?", (state, state, unit_id))
            # Retain bounded history, never delete pending or uncertain work.
            db.execute("DELETE FROM units WHERE state IN ('completed','failed') AND id NOT IN "
                       "(SELECT id FROM units ORDER BY created DESC LIMIT 500)")

    def recover(self):
        with self.connect() as db:
            # An abrupt failure may have committed an external side effect. Never replay it blindly.
            db.execute("UPDATE units SET state='interrupted' WHERE state='running'")
            return db.execute("SELECT id,kind,payload FROM units WHERE state='queued' ORDER BY created").fetchall()

    def status(self):
        with self.connect() as db:
            db.execute('BEGIN')
            counts = dict(db.execute('SELECT state,count(*) FROM units GROUP BY state'))
            mode = db.execute('SELECT mode FROM control WHERE id=1').fetchone()[0]
        active = counts.get('running', 0)
        state = ('draining' if active else 'stopping') if mode == 'stopping' else (
            ('pausing' if active else 'paused') if mode == 'paused' else 'running')
        return {'processing': state, 'running_jobs': active, 'remaining_jobs': counts.get('queued', 0),
                'completed_jobs': counts.get('completed', 0), 'failed_jobs': counts.get('failed', 0),
                'interrupted_jobs': counts.get('interrupted', 0), 'total_jobs': None}


def store():
    path = os.environ.get('DACHAPPLY_CONTROL_DB')
    return Store(path) if path else None


def accepting():
    control = store()
    return control is None or control.mode() == 'running'


def tracked(kind):
    def decorate(function):
        key = 'document-' + function.__name__.removeprefix('_run').strip('_') if function.__name__ != '_run' else 'documents'
        _handlers[key] = function
        @functools.wraps(function)
        def wrapped(*args, **kwargs):
            control = store()
            if control is not None and not getattr(_local, 'active', False):
                return execute_document(*admit_document(control, key, function, args, kwargs))
            with active_unit(kind):
                return function(*args, **kwargs)
        def submit(*args, **kwargs):
            # Admit on the caller before spawning: shutdown cannot outrun persistence.
            admitted = admit_document(store(), key, function, args, kwargs)
            threading.Thread(target=execute_document, args=admitted, daemon=True).start()
        wrapped.submit = submit
        return wrapped
    return decorate


def admit_document(control, kind, function, args, kwargs):
    from jobradar.services import cv_tasks
    from pathlib import Path
    bound = inspect.signature(function).bind(*args, **kwargs)
    values = dict(bound.arguments)
    values.pop('cancel_event', None)
    callback = values.pop('on_finish', None)
    finish = None
    if callback:
        closure = inspect.getclosurevars(callback).nonlocals
        finish = {name: closure[name] for name in ('job_id', 'user_id', 'key')}
    with cv_tasks._lock:
        snapshot = {name: value for name, value in cv_tasks._tasks[values['task_id']].items()
                    if name not in ('_cancel', 'archive')}
    payload = json.loads(json.dumps({'document': values, 'snapshot': snapshot, 'finish': finish},
        default=lambda value: str(value) if isinstance(value, Path) else (
            {'_queue_bytes': base64.b64encode(value).decode('ascii')} if isinstance(value, bytes) else _not_json(value))))
    return control, control.enqueue(kind, payload), kind, payload, bound.arguments


def _not_json(value):
    raise TypeError('Unsupported document queue value: ' + type(value).__name__)


def restore_document(payload):
    from jobradar.services import cv_tasks, application_prep
    values = json.loads(json.dumps(payload['document']), object_hook=lambda value:
        base64.b64decode(value['_queue_bytes']) if set(value) == {'_queue_bytes'} else value)
    task_id = values['task_id']
    snapshot = dict(payload['snapshot'])
    snapshot['_cancel'] = threading.Event()
    snapshot['archive'] = None
    snapshot['_estimate_key'] = tuple(snapshot.get('_estimate_key') or ())
    with cv_tasks._lock:
        cv_tasks._tasks[task_id] = snapshot
    values['cancel_event'] = snapshot['_cancel']
    finish = payload.get('finish')
    if finish:
        with application_prep._lock:
            application_prep._running += 1
        values['on_finish'] = lambda task_id: application_prep._finish(finish['job_id'], finish['user_id'], finish['key'], task_id)
    return values


def execute_document(control, unit_id, kind, payload, live):
    if unit_id is None:
        return
    from jobradar.services import cv_tasks
    values = dict(live)
    task_id = values['task_id']
    while not control.claim(unit_id, kind, 1000):
        time.sleep(.1)
    _local.active = True
    event('unit_started', 'documents')
    try:
        _handlers[kind](**values)
    finally:
        with cv_tasks._lock:
            failed = cv_tasks._tasks.get(task_id, {}).get('status') != 'ready'
        control.finish(unit_id, 'failed' if failed else 'completed')
        event('unit_failed' if failed else 'unit_completed', 'documents')
        _local.active = False


@contextmanager
def active_unit(kind):
    """Ephemeral task admission; document sidecars remain their durable queue."""
    control = store()
    if control is None or getattr(_local, 'active', False):
        yield
        return
    unit_id = control.enqueue(kind, {'ephemeral': uuid.uuid4().hex})
    while not control.claim(unit_id, kind, 1000):
        time.sleep(.1)
    event('unit_started', kind)
    _local.active = True
    try:
        yield
    except BaseException:
        control.finish(unit_id, 'failed')
        event('unit_failed', kind)
        raise
    else:
        control.finish(unit_id)
        event('unit_completed', kind)
    finally:
        _local.active = False


def durable(kind, limit=1):
    """Only JSON IDs/flags are persisted; never candidate text, credentials or callables."""
    def decorate(function):
        _handlers[kind] = function

        @functools.wraps(function)
        def wrapped(*args, **kwargs):
            control = store()
            if control is None or getattr(_local, 'active', False):
                return function(*args, **kwargs)
            unit_id = control.enqueue(kind, {'args': args, 'kwargs': kwargs})
            if unit_id is None:
                return None
            return execute(control, unit_id, kind, args, kwargs, limit)
        def submit(*args, **kwargs):
            control = store()
            if control is None:
                raise RuntimeError('Durable submit requires the local supervisor')
            unit_id = control.enqueue(kind, {'args': args, 'kwargs': kwargs})
            if unit_id:
                threading.Thread(target=execute, args=(control, unit_id, kind, args, kwargs, limit), daemon=True).start()
        wrapped.submit = submit
        return wrapped
    return decorate


def execute(control, unit_id, kind, args, kwargs, limit=1):
    while not control.claim(unit_id, kind, limit):
        time.sleep(.1)
    event('unit_started', kind)
    _local.active = True
    try:
        result = _handlers[kind](*args, **kwargs)
    except BaseException:
        control.finish(unit_id, 'failed')
        event('unit_failed', kind)
        raise
    else:
        failed = result is False or bool(getattr(result, 'error', ''))
        if isinstance(result, tuple) and result:
            failed = bool(getattr(result[0], 'error', ''))
        control.finish(unit_id, 'failed' if failed else 'completed')
        event('unit_failed' if failed else 'unit_completed', kind)
        return result
    finally:
        _local.active = False


def recover_pending():
    control = store()
    if control is None:
        return
    from jobradar.services import application_prep, mailbox  # registers allowlisted handlers
    for unit_id, kind, payload in control.recover():
        data = json.loads(payload)
        if 'document' in data:
            # Register restored tasks before sidecar recovery can admit them a second time.
            live = restore_document(data)
            threading.Thread(target=execute_document, args=(control, unit_id, kind, data, live), daemon=True).start()
            continue
        if 'ephemeral' in data:
            # The document sidecar is restored by application_prep.resume_queue.
            control.finish(unit_id, 'interrupted')
            continue
        if kind not in _handlers:
            continue
        args, kwargs = data['args'], data['kwargs']
        if kind == 'pipeline':
            application_prep._piping.add(args[0])
        elif kind == 'requirements':
            application_prep._analysing.add(args[0])
        threading.Thread(target=execute, args=(control, unit_id, kind, args, kwargs), daemon=True).start()
