"""TASK-356: the Neon project's usage, read from Neon's control-plane API, with an email at each 5% step.

Started only by `manage.py dashboard_runtime`, in its own daemon thread, at most once an hour. It must
never touch the database (no ORM, no connection), because a check that woke Neon would spend what it
measures. State is one private JSON file beside the control database, so a restart repeats nothing and
the localhost app list can read the same numbers.

The Neon fields are the documented ones, not checked against a real key: a missing or malformed field is
shown as unknown and sends nothing. The API key goes in one header and nowhere else: failures record an
HTTP status or a fixed sentence, never an exception's text.
"""
import json
import logging
import math
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from threading import Thread
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import HTTPRedirectHandler, Request, build_opener

from django.conf import settings
from django.core.mail import send_mail

from jobradar.services.cv_generator import _write_json

logger = logging.getLogger(__name__)

API = 'https://console.neon.tech/api/v2'
CHECK_SECONDS = 3600
STEP = 5
GB = 1_000_000_000  # decimal, so the percentages err towards warning early
TRANSFER_LIMIT_GB = 5
COMPUTE_LIMIT_HOURS = 100
STORAGE_LIMIT_GB = 1
# metric: (label, Neon field, units per Neon's number, limit, unit)
METRICS = {'transfer': ('Transfer', 'data_transfer_bytes', GB, TRANSFER_LIMIT_GB, 'GB'),
           'compute': ('Compute', 'compute_time_seconds', 3600, COMPUTE_LIMIT_HOURS, 'hours'),
           'storage': ('Storage', 'synthetic_storage_size', GB, STORAGE_LIMIT_GB, 'GB')}


def state_path():
    control = os.environ.get('DACHAPPLY_CONTROL_DB')
    return Path(control).parent / 'db-usage.json' if control else None


def configured():
    return bool(settings.NEON_API_KEY and settings.NEON_PROJECT_ID and state_path())


def read_state():
    path = state_path()
    try:
        data = json.loads(path.read_text(encoding='utf-8')) if path else {}
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_state(state):
    # Replacing fails on Windows while a reader has the file open, and a lost write would repeat an email.
    for _ in range(5):
        if _write_json(state_path(), state):
            return
        time.sleep(.2)
    logger.warning('Could not save the database usage state')


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None  # urllib would send the Authorization header on to the redirect's host


def fetch_project():
    request = Request(f'{API}/projects/{quote(settings.NEON_PROJECT_ID, safe="")}',
                      headers={'Authorization': f'Bearer {settings.NEON_API_KEY}', 'Accept': 'application/json'})
    with build_opener(_NoRedirect).open(request, timeout=30) as response:
        body = json.load(response)
    project = body.get('project', body)
    if not isinstance(project, dict):
        raise ValueError('unexpected response')
    return project


def _metrics(project):
    metrics = {}
    for name, (label, field, units, limit, unit) in METRICS.items():
        value = project.get(field)
        known = isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0
        used = value / units if known else None
        metrics[name] = {'label': label, 'used': round(used, 3) if known else None, 'limit': limit, 'unit': unit,
                         'percent': round(used / limit * 100, 2) if known else None}
    return metrics


def _period_day(period):
    # A date, so a reformatted timestamp of the same period can never reset the steps and resend them.
    return str(period.get('start') or '')[:10]


def _alert(state):
    """One email per metric that reached a new step, naming the current step. A step counts as sent only
    once it was: an unsent one retries on the next check."""
    owner = settings.DB_USAGE_OWNER_EMAIL
    if not owner:
        return
    for name, metric in state['metrics'].items():
        if metric['percent'] is None:
            continue
        step = int(metric['percent'] // STEP) * STEP
        if step <= state['sent'].get(name, 0):
            continue
        amount = f"{metric['used']} of {metric['limit']} {metric['unit']} ({metric['percent']}%)"
        try:
            send_mail(f"Neon {metric['label'].lower()} reached {step}%", f"{metric['label']} this billing period: {amount}.", None, [owner])
        except Exception as exc:
            logger.warning('Database usage email failed: %s', type(exc).__name__)
            continue
        state['sent'][name] = step
        _write_state(state)


def check():
    """One read of Neon. A failed read keeps the last good numbers and says so."""
    state = read_state()
    state['attempted_at'] = datetime.now(timezone.utc).isoformat()
    try:
        project = fetch_project()
    except Exception as exc:
        state['error'] = f'Neon answered {exc.code}' if isinstance(exc, HTTPError) else 'Could not read usage from Neon'
        logger.warning('Database usage check failed: %s', state['error'])
        _write_state(state)
        return state
    before = state.get('period') or {}
    period = {'start': project.get('consumption_period_start') or before.get('start'),
              'end': project.get('consumption_period_end') or before.get('end')}
    if _period_day(before) and _period_day(period) != _period_day(before):
        state['sent'] = {}  # a new billing period starts the steps again
    state.setdefault('sent', {})
    state.update(metrics=_metrics(project), period=period, checked_at=state['attempted_at'], error='')
    _write_state(state)
    _alert(state)
    return state


def seconds_until_due():
    """Time left on the hour, from the saved attempt, so restarting cannot add a check."""
    try:
        last = datetime.fromisoformat(read_state().get('attempted_at'))
    except (TypeError, ValueError):
        return 0
    return max(0, CHECK_SECONDS - (datetime.now(timezone.utc) - last).total_seconds())


def _loop():
    time.sleep(seconds_until_due())
    while True:
        try:
            check()
        except Exception as exc:
            logger.warning('Database usage check failed: %s', type(exc).__name__)
        time.sleep(CHECK_SECONDS)


def start():
    if configured():
        Thread(target=_loop, name='dachapply-db-usage', daemon=True).start()


def is_owner(user):
    owner = settings.DB_USAGE_OWNER_EMAIL.lower()
    return bool(owner) and (getattr(user, 'email', '') or '').strip().lower() == owner


def public_state():
    """What the panel shows. Reads the file only."""
    if not configured():
        return {'configured': False}
    state = read_state()
    return {'configured': True, **{key: state.get(key) for key in ('checked_at', 'attempted_at', 'error', 'period', 'metrics')}}
