# TASK-372.2: explicit maintenance entrypoint, no daemon or model calls.
import json

from django.core.management.base import BaseCommand, CommandError

from jobradar.services.error_triage import triage


class Command(BaseCommand):
    help = 'Triage changed unresolved local errors; --list shows the unresolved maintenance queue.'
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--list', action='store_true', dest='list_only')

    def handle(self, *args, **options):
        try:
            self.stdout.write(json.dumps(triage(dry_run=options['dry_run'], list_only=options['list_only']), sort_keys=True))
        except Exception:
            raise CommandError('Local error triage failed; checkpoint retained, retry after checking store/CLI availability.') from None
