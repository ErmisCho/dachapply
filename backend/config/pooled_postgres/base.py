"""TASK-282: Django's PostgreSQL backend with a pool health check that skips recently used connections.

With CONN_HEALTH_CHECKS on, Django gives the TASK-281 pool ConnectionPool.check_connection: an
empty query on EVERY checkout, i.e. one more Neon round trip (~27 ms) per request, invisible in
Server-Timing's db figure because it runs below Django's cursor wrapper. It only matters for a
connection Neon closed while idle (compute suspends after 5 idle minutes), so a connection handed
out less than RECENT seconds ago skips it. A drop inside that window fails that one request, and the
pool discards the broken connection when it comes back. Used only where with_db_pool adds the pool.
"""
import weakref
from time import monotonic

from django.db.backends.postgresql import base
from psycopg_pool import ConnectionPool

RECENT = 60.0  # well inside Neon's 5-minute suspend
_handed_out = weakref.WeakKeyDictionary()


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
