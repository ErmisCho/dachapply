"""TASK-282: Django's PostgreSQL backend with a pool health check that skips recently used connections.

With CONN_HEALTH_CHECKS on, Django gives the TASK-281 pool ConnectionPool.check_connection: an
empty query on EVERY checkout, i.e. one more Neon round trip (~27 ms) per request, invisible in
Server-Timing's db figure because it runs below Django's cursor wrapper. It only matters for a
connection Neon closed while idle (compute suspends after 5 idle minutes), so a connection handed
out less than RECENT seconds ago skips it. A drop inside that window fails that one request, and the
pool discards the broken connection when it comes back. Used only where with_db_pool adds the pool.
"""
import json
import re
import sys
import threading
import weakref
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic

from django.conf import settings
from django.db.backends.postgresql import base
from psycopg_pool import ConnectionPool, PoolTimeout

RECENT = 60.0  # well inside Neon's 5-minute suspend
_handed_out = weakref.WeakKeyDictionary()
# TASK-415: who holds each checked-out connection, so a PoolTimeout can name them.
_holders = {}  # id(conn) -> (thread name, thread ident, checkout time, app frames)
_APP_FILE = re.compile(r'[\\/]jobradar[\\/]')


def _where():
    """The three innermost jobradar frames as module.function:line; code identifiers only."""
    out, frame = [], sys._getframe(2)
    while frame is not None and len(out) < 3:
        code = frame.f_code
        if _APP_FILE.search(code.co_filename):
            out.append(f'{Path(code.co_filename).stem}.{code.co_name}:{frame.f_lineno}')
        frame = frame.f_back
    return out


def record_pool_timeout(pool):
    """Append pool stats and current holders to pool-timeouts.jsonl beside the local occurrence store."""
    store = settings.ERROR_OCCURRENCE_LOCAL_DB
    if not store or not Path(store).parent.is_dir():
        return  # TASK-372.1: only where the owner provisioned the private directory
    now, alive = monotonic(), {t.ident for t in threading.enumerate()}
    holders = sorted(({'thread': name, 'alive': ident in alive, 'held_s': round(now - since, 1), 'where': where}
                      for name, ident, since, where in list(_holders.values())), key=lambda h: -h['held_s'])
    entry = {'at': datetime.now(timezone.utc).isoformat(), 'stats': pool.get_stats(), 'holders': holders}
    try:
        with open(Path(store).parent / 'pool-timeouts.jsonl', 'a', encoding='utf-8') as out:
            out.write(json.dumps(entry) + '\n')
    except OSError:
        pass  # diagnostics must never turn the timeout into a different error


def check_unless_recent(conn):
    now = monotonic()
    last = _handed_out.get(conn)
    if last is None or now - last >= RECENT:
        ConnectionPool.check_connection(conn)
    _handed_out[conn] = now


class DatabaseWrapper(base.DatabaseWrapper):
    @property
    def pool(self):
        pool = super().pool
        # Django passes check= to ConnectionPool itself (a second one in OPTIONS is a TypeError),
        # so the check is swapped on the pool it built. CONN_HEALTH_CHECKS off leaves None alone.
        if pool is not None and pool._check is ConnectionPool.check_connection:
            pool._check = check_unless_recent
        return pool

    def get_new_connection(self, conn_params):
        try:
            conn = super().get_new_connection(conn_params)
        except PoolTimeout:
            record_pool_timeout(self.pool)
            raise
        if self.pool:
            thread = threading.current_thread()
            _holders[id(conn)] = (thread.name, thread.ident, monotonic(), _where())
        return conn

    def _close(self):
        if self.connection is not None:
            _holders.pop(id(self.connection), None)
        return super()._close()
