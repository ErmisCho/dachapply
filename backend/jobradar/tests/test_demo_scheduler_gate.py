"""TASK-273: the demo scheduler must never start inside a test run, however pytest was launched."""
import sys

from jobradar.services import demo_scheduler


def test_scheduler_does_not_start_under_python_dash_m_pytest(monkeypatch):
    # `python -m pytest` leaves argv[0] as '__main__.py' with no 'pytest' argument.
    monkeypatch.setattr(sys, 'argv', ['C:/venv/Lib/site-packages/pytest/__main__.py', '-q'])
    monkeypatch.delenv('DACHAPPLY_DEMO_SEED_SCHEDULER', raising=False)
    assert demo_scheduler._should_start_scheduler() is False
