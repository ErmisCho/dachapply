"""TASK-273: the demo scheduler must never start inside a test run, however pytest was launched."""
import sys

import pytest

from jobradar.services import demo_scheduler


def test_scheduler_does_not_start_under_python_dash_m_pytest(monkeypatch):
    # `python -m pytest` leaves argv[0] as '__main__.py' with no 'pytest' argument.
    monkeypatch.setattr(sys, 'argv', ['C:/venv/Lib/site-packages/pytest/__main__.py', '-q'])
    monkeypatch.delenv('DACHAPPLY_DEMO_SEED_SCHEDULER', raising=False)
    assert demo_scheduler._should_start_scheduler() is False


# TASK-276: one shared runserver-only predicate gates both in-process loops (demo seed + mailbox).
@pytest.mark.parametrize('argv, run_main, env, expected', [
    (['manage.py', 'runserver'], 'true', {}, True),
    (['manage.py', 'runserver', '--noreload'], None, {}, True),
    (['manage.py', 'runserver'], None, {}, False),  # autoreloader parent: the child starts it, once
    (['/app/.venv/bin/gunicorn', 'config.wsgi:application', '--bind', '0.0.0.0:8000'], None, {}, False),
    (['manage.py', 'migrate'], 'true', {}, False),
    (['manage.py', 'runserver'], 'true', {'DACHAPPLY_DEMO_SEED_SCHEDULER': '0', 'DACHAPPLY_LOCAL_MAILBOX_LOOP': '0'}, False),
])
@pytest.mark.parametrize('env_var', ['DACHAPPLY_DEMO_SEED_SCHEDULER', 'DACHAPPLY_LOCAL_MAILBOX_LOOP'])
def test_local_loops_start_only_under_runserver(monkeypatch, argv, run_main, env, expected, env_var):
    monkeypatch.delitem(sys.modules, 'pytest')  # otherwise the pytest guard answers every case
    monkeypatch.setattr(sys, 'argv', argv)
    for name in ('RUN_MAIN', 'DACHAPPLY_DEMO_SEED_SCHEDULER', 'DACHAPPLY_LOCAL_MAILBOX_LOOP'):
        monkeypatch.delenv(name, raising=False)
    if run_main:
        monkeypatch.setenv('RUN_MAIN', run_main)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    assert demo_scheduler.should_start_local_loop(env_var) is expected


def test_local_loops_never_start_under_pytest(monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['manage.py', 'runserver'])
    monkeypatch.setenv('RUN_MAIN', 'true')
    assert demo_scheduler.should_start_local_loop('DACHAPPLY_LOCAL_MAILBOX_LOOP') is False
