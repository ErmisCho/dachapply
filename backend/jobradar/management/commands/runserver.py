"""runserver whose startup survives a slow or unreachable database.

Django's runserver runs check_migrations() on its serving thread before it binds the port; an
OperationalError there (the TASK-281 pool's 10 s getconn timeout, seen 2026-10-17/18 at startup
after Neon or the network was slow) killed that thread and left a process that never listened:
"caren refused to connect" until someone restarted it. The migration check is only a warning, so
it is skipped with a message instead; requests then get their own connections (and retries).
"""
from django.contrib.staticfiles.management.commands.runserver import Command as StaticfilesRunserver
from django.db import DatabaseError


class Command(StaticfilesRunserver):
    def check_migrations(self):
        try:
            super().check_migrations()
        except DatabaseError as exc:
            self.stderr.write(f'Skipped the unapplied-migrations check: database not reachable yet ({exc}).')
