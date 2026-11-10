"""Local supervisor's cooperative gate. Never suspend a process or interrupt a safe unit."""
import hashlib
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
_limits = {}  # kind -> durable()'s limit: a number, or a function of the unit's args read at each claim (TASK-358)
# TASK-358: automatic analyses share one admission limit, the account's analysis_concurrency
# (application_prep._lane): a daily-document unit runs its requirements analysis inline.
ANALYSES = ('pipeline', 'requirements', 'daily-document')


def event(name, kind='runtime'):
    logging.getLogger('dashboard.events').info(json.dumps({
        'time': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'event': name, 'kind': kind}))


def job_key(kind, payload):
    """Stable logical identity: retries may use a new thread/task ID."""
    if kind == 'daily-tick':
        return None
    args, kwargs = payload.get('args', []), payload.get('kwargs', {})
    if kind in ('mailbox', 'mailbox-tick'):
        if not kwargs.get('force', args[0] if args else False):
            return None
        identity = ['mailbox']
    elif kind in ('pipeline', 'requirements', 'daily-document'):
        identity = [kind, kwargs.get('job_id', args[0] if args else None),
                    kwargs.get('user_id', args[1] if len(args) > 1 else None)]
    elif payload.get('finish'):
        identity = [kind, payload['finish']]
    elif 'document' in payload:
        document = dict(payload['document'])
        document.pop('task_id', None)
        identity = [kind, document]
    else:
        identity = [kind, payload]
    return hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()


def report_mailbox_job(owner_id):
    """Promote an actual mailbox check, never an empty scheduler wake, to a job."""
    control = store()
    unit_id = getattr(_local, 'unit_id', None)
    if control is not None and unit_id:
        control.set_job_key(unit_id, 'mailbox:' + str(owner_id))


def handoff_documents(job_id=None, user_id=None):
    """Called under preparation's status lock as variants replace their daily request."""
    control = store()
    unit_id = getattr(_local, 'unit_id', None)
    if control is not None:
        with control.connect() as db:
            if job_id is not None and user_id is not None:
                key = job_key('daily-document', {'args': [job_id, user_id]})
                db.execute("UPDATE units SET state='resolved',payload='{}' WHERE state='interrupted' AND job_key=?", (key,))
            if unit_id and getattr(_local, 'kind', None) == 'daily-document':
                db.execute('UPDATE units SET job_key=NULL WHERE id=?', (unit_id,))


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
            db.execute('BEGIN IMMEDIATE')
            if 'job_key' not in {row[1] for row in db.execute('PRAGMA table_info(units)')}:
                db.execute('ALTER TABLE units ADD COLUMN job_key TEXT')
                for unit_id, kind, payload, state in db.execute('SELECT id,kind,payload,state FROM units').fetchall():
                    key = None if kind == 'daily-document' and state == 'completed' else job_key(kind, json.loads(payload))
                    db.execute('UPDATE units SET job_key=? WHERE id=?', (key, unit_id))
            if db.execute('PRAGMA user_version').fetchone()[0] < 2:
                # Upgrade waiting daily requests hidden by the previous counter policy.
                for unit_id, payload in db.execute("SELECT id,payload FROM units WHERE kind='daily-document' AND state='queued'").fetchall():
                    db.execute('UPDATE units SET job_key=? WHERE id=?', (job_key('daily-document', json.loads(payload)), unit_id))
                db.execute('PRAGMA user_version=2')

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
            cursor = db.execute('INSERT OR IGNORE INTO units (id,kind,payload,state,created,job_key) VALUES (?, ?, ?, ?, ?, ?)',
                                (unit_id, kind, identity, 'queued', time.time(), job_key(kind, payload)))
            return unit_id if cursor.rowcount else None

    def claim(self, unit_id, kind, limit):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT mode FROM control WHERE id=1').fetchone()[0] != 'running':
                return False
            # These workers share application_prep's analysis lanes. A waiting worker is queued,
            # so Pause must prevent it becoming the next safe unit after a lane is released.
            if kind in ANALYSES:
                active = db.execute(f"SELECT count(*) FROM units WHERE kind IN ({','.join('?' * len(ANALYSES))}) AND state='running'", ANALYSES).fetchone()[0]
            else:
                active = db.execute("SELECT count(*) FROM units WHERE kind=? AND state='running'", (kind,)).fetchone()[0]
            if active >= limit:
                return False
            return bool(db.execute("UPDATE units SET state='running' WHERE id=? AND state='queued'", (unit_id,)).rowcount)

    def active_units(self):
        with self.connect() as db:
            return db.execute("SELECT count(*) FROM units WHERE state='running'").fetchone()[0]

    def set_job_key(self, unit_id, key):
        with self.connect() as db:
            db.execute('UPDATE units SET job_key=? WHERE id=?', (key, unit_id))

    def finish(self, unit_id, state='completed', *, count_job=True):
        with self.connect() as db:
            if state == 'completed':
                db.execute("UPDATE units SET state='resolved',payload='{}' WHERE state='interrupted' "
                           "AND job_key=(SELECT job_key FROM units WHERE id=?)", (unit_id,))
            db.execute("UPDATE units SET state=?, payload=CASE WHEN ? IN ('completed','failed','cancelled','resolved') THEN '{}' ELSE payload END WHERE id=?", (state, state, unit_id))
            if state == 'completed':
                db.execute("UPDATE units SET job_key=NULL WHERE id=? AND (kind='daily-document' OR ?=0)", (unit_id, count_job))
            # Retain bounded history, never delete pending or uncertain work.
            db.execute("DELETE FROM units WHERE state IN ('completed','failed','cancelled','resolved') AND id NOT IN "
                       "(SELECT id FROM units ORDER BY created DESC LIMIT 500)")

    def cancel_document(self, task_id, user_id):
        """Persist the request before HTTP acknowledges it; the serving thread owns its Event."""
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            for unit_id, raw in db.execute("SELECT id,payload FROM units WHERE state IN ('queued','running')"):
                payload = json.loads(raw)
                document = payload.get('document', {})
                if document.get('task_id') == task_id and document.get('user_id') == user_id:
                    payload['cancel_requested'] = True
                    payload['snapshot'].update(status='cancelling', stage='Cancelling', _stage_key='cancelling')
                    db.execute('UPDATE units SET payload=? WHERE id=?',
                               (json.dumps(payload, sort_keys=True, separators=(',', ':')), unit_id))
                    return True
        return False

    def schedule(self, unit_id, snapshot):
        """TASK-359: keep a usage-limited manual document, inputs and all, until its retry; the snapshot
        carries its status, line and retry_at, so recover restores it waiting rather than running it."""
        with self.connect() as db:
            payload = json.loads(db.execute('SELECT payload FROM units WHERE id=?', (unit_id,)).fetchone()[0])
            payload['snapshot'] = snapshot
            db.execute("UPDATE units SET state='scheduled', payload=? WHERE id=?",
                       (json.dumps(payload, sort_keys=True, separators=(',', ':'), default=str), unit_id))

    def recover(self):
        with self.connect() as db:
            # An abrupt failure may have committed an external side effect. Never replay it blindly.
            db.execute("UPDATE units SET state='interrupted' WHERE state='running'")
            return db.execute("SELECT id,kind,payload FROM units WHERE state IN ('queued','scheduled') ORDER BY created").fetchall()

    def status(self):
        with self.connect() as db:
            db.execute('BEGIN')
            counts = dict(db.execute('SELECT state,count(*) FROM units WHERE job_key IS NOT NULL GROUP BY state'))
            active = db.execute("SELECT count(*) FROM units WHERE state='running'").fetchone()[0]
            mode = db.execute('SELECT mode FROM control WHERE id=1').fetchone()[0]
        state = ('draining' if active else 'stopping') if mode == 'stopping' else (
            ('pausing' if active else 'paused') if mode == 'paused' else 'running')
        return {'processing': state, 'running_jobs': counts.get('running', 0), 'remaining_jobs': counts.get('queued', 0),
                'completed_jobs': counts.get('completed', 0), 'failed_jobs': counts.get('failed', 0),
                'cancelled_jobs': counts.get('cancelled', 0),
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
    from jobradar.services import cv_tasks, application_prep
    from pathlib import Path
    bound = inspect.signature(function).bind(*args, **kwargs)
    values = dict(bound.arguments)
    values.pop('cancel_event', None)
    callback = values.pop('on_finish', None)
    finish = None
    if callback:
        if not isinstance(callback, functools.partial) or callback.func not in (application_prep._finish, application_prep._adjusted):
            raise TypeError('Unsupported document completion callback')
        finish = dict(zip(('job_id', 'user_id', 'key'), callback.args))
        finish['action'] = 'finish' if callback.func is application_prep._finish else 'adjusted'
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
    if payload.get('cancel_requested'):
        snapshot['_cancel'].set()
    snapshot['archive'] = None
    snapshot['_estimate_key'] = tuple(snapshot.get('_estimate_key') or ())
    with cv_tasks._lock:
        cv_tasks._tasks[task_id] = snapshot
    values['cancel_event'] = snapshot['_cancel']
    finish = payload.get('finish')
    if finish:
        if finish['action'] == 'finish':
            with application_prep._lock:
                application_prep._running += 1
        callback = application_prep._finish if finish['action'] == 'finish' else application_prep._adjusted
        values['on_finish'] = functools.partial(callback, finish['job_id'], finish['user_id'], finish['key'])
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
        if values['cancel_event'].is_set():
            # Never enter a compiler/model handler for work cancelled while queued.
            cv_tasks._update(task_id, status='cancelled', stage='Cancelled', error='')
            if values.get('on_finish'):
                values['on_finish'](task_id)
        else:
            _handlers[kind](**values)
    finally:
        with cv_tasks._lock:
            task = cv_tasks._tasks.get(task_id, {})
            status = task.get('status')
            if status == 'scheduled':  # TASK-359: cv_tasks.rerun resolves this unit when it runs again
                task['_unit'] = unit_id
                snapshot = {name: value for name, value in task.items() if name not in ('_cancel', 'archive')}
        if status == 'scheduled':
            control.schedule(unit_id, snapshot)
        else:
            outcome = 'completed' if status == 'ready' else 'cancelled' if status == 'cancelled' else 'failed'
            control.finish(unit_id, outcome)
            event('unit_' + outcome, 'documents')
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
    """Only JSON IDs/flags are persisted; never candidate text, credentials or callables. `limit`: how many units of
    this kind run at once, or a function of the unit's args giving that (TASK-358)."""
    def decorate(function):
        _handlers[kind] = function
        _limits[kind] = limit

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
            return unit_id
        wrapped.submit = submit
        return wrapped
    return decorate


def execute(control, unit_id, kind, args, kwargs, limit=None):
    limit = _limits.get(kind, 1) if limit is None else limit  # recover_pending passes none: the kind's own
    while not control.claim(unit_id, kind, limit(*args, **kwargs) if callable(limit) else limit):
        time.sleep(.1)
    event('unit_started', kind)
    _local.active = True
    _local.unit_id = unit_id
    _local.kind = kind
    try:
        result = _handlers[kind](*args, **kwargs)
    except BaseException:
        control.finish(unit_id, 'failed')
        event('unit_failed', kind)
        raise
    else:
        actual = result[0] if isinstance(result, tuple) and result else result
        manual = kwargs.get('force', args[0] if args else False) or (
            isinstance(result, tuple) and len(result) > 1 and result[1] is not None)
        empty_poll = not manual and getattr(actual, 'fetched_count', None) == 0 and not getattr(actual, 'error', '')
        if (kind in ('mailbox', 'mailbox-tick') and (actual is None or getattr(actual, 'skipped', False))
                or kind in ('pipeline', 'requirements', 'interview-prep') and actual is None):
            control.set_job_key(unit_id, None)
        failed = result is False or bool(getattr(result, 'error', ''))
        if isinstance(result, tuple) and result:
            failed = bool(getattr(result[0], 'error', ''))
        control.finish(unit_id, 'failed' if failed else 'completed',
                       count_job=not (kind in ('mailbox', 'mailbox-tick') and empty_poll))
        event('unit_failed' if failed else 'unit_completed', kind)
        return result
    finally:
        _local.active = False
        _local.unit_id = None
        _local.kind = None


def recover_pending():
    control = store()
    if control is None:
        return
    from jobradar.services import application_prep, cv_tasks, interview_prep, mailbox  # registers allowlisted handlers
    for unit_id, kind, payload in control.recover():
        data = json.loads(payload)
        if 'document' in data:
            # Register restored tasks before sidecar recovery can admit them a second time.
            live = restore_document(data)
            if data['snapshot'].get('status') == 'scheduled':
                cv_tasks._reruns[live['task_id']] = live  # TASK-359: resume_queue's retry_due runs it at retry_at
                continue
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
        elif kind == 'interview-prep':
            interview_prep._active.add(args[0])
        threading.Thread(target=execute, args=(control, unit_id, kind, args, kwargs), daemon=True).start()
