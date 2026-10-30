"""TASK-347: the demo scheduler touches the database once per local day, inside 08:00-20:00."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from jobradar.services import demo_scheduler


def test_a_day_of_wakes_touches_the_database_once_inside_the_window(db, monkeypatch):
    clock = {'now': datetime(2026, 11, 4, 0, 0, tzinfo=ZoneInfo('Europe/Vienna'))}
    monkeypatch.setattr(timezone, 'now', lambda: clock['now'])
    seeded = []
    monkeypatch.setattr(demo_scheduler, 'seed_demo_if_due', lambda: seeded.append(clock['now']))  # ensure_demo_user is heavy
    touched = []  # send_due_digests stays real: its ScheduledTaskRun claim is the DB work being counted
    end = clock['now'] + timedelta(days=2)
    while clock['now'] < end:
        with CaptureQueriesContext(connection) as queries:
            seconds = demo_scheduler.scheduler_tick()
        if queries:
            touched.append(timezone.localtime(clock['now']))
        clock['now'] += timedelta(seconds=seconds)
    assert [t.strftime('%d %H:%M') for t in touched] == ['04 08:00', '05 08:00']
    assert seeded == [t for t in touched]


def test_a_database_error_retries_soon_and_backs_off(db, monkeypatch):
    from django.db import OperationalError
    clock = {'now': datetime(2026, 11, 4, 8, 0, tzinfo=ZoneInfo('Europe/Vienna'))}
    monkeypatch.setattr(timezone, 'now', lambda: clock['now'])
    monkeypatch.setattr(demo_scheduler, 'seed_demo_if_due', lambda: None)

    def down():
        raise OperationalError('quota exceeded')
    monkeypatch.setattr(demo_scheduler, 'send_due_digests', down)
    sleeps = []
    for _ in range(3):
        sleeps.append(demo_scheduler.scheduler_tick())
        clock['now'] += timedelta(seconds=sleeps[-1])
    assert sleeps == [60, 120, 240]
    monkeypatch.setattr(demo_scheduler, 'send_due_digests', lambda: 0)
    demo_scheduler.scheduler_tick()
    assert demo_scheduler._failures == 0 and demo_scheduler._done_on == clock['now'].date()
