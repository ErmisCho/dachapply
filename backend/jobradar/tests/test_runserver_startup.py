from io import StringIO

from django.core.management import get_commands
from django.db import OperationalError

from jobradar.management.commands import runserver


def test_runserver_starts_even_when_the_database_is_not_reachable_yet(monkeypatch):
    """2026-10-18: a pool timeout in check_migrations left a server that never bound its port."""
    assert get_commands()['runserver'] == 'jobradar'

    def unreachable(self):
        raise OperationalError("couldn't get a connection after 10.00 sec")

    monkeypatch.setattr(runserver.StaticfilesRunserver, 'check_migrations', unreachable)
    command = runserver.Command(stderr=StringIO())
    command.check_migrations()  # must not raise: the serving thread goes on to bind the port
    assert 'database not reachable yet' in command.stderr._out.getvalue()
