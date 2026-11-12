# TASK-372.2: explicit maintenance entrypoint, no daemon or model calls.
import json

from django.core.management.base import BaseCommand, CommandError

from jobradar.services.error_triage import triage, resolve  # TASK-372.3


class Command(BaseCommand):
    help = 'Triage changed unresolved local errors; --list shows the unresolved maintenance queue.'
    requires_system_checks = []

    def add_arguments(self, parser):
        # TASK-372.3: explicit attested completion, never inferred from Done alone.
        parser.add_argument('--resolve', metavar='TASK_ID')
        for name in ('fix', 'tests', 'evaluation', 'merge', 'fixed-build'):
            parser.add_argument('--' + name)
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--list', action='store_true', dest='list_only')

    def handle(self, *args, **options):
        try:
            if options['resolve']:
                if options['dry_run'] or options['list_only']:
                    raise ValueError('resolution cannot be combined with preview')
                result = resolve(options['resolve'], **{k: options[k] or '' for k in ('fix', 'tests', 'evaluation', 'merge', 'fixed_build')})
                self.stdout.write(json.dumps(result))
                return
            self.stdout.write(json.dumps(triage(dry_run=options['dry_run'], list_only=options['list_only']), sort_keys=True))
        except Exception:
            raise CommandError('Local error triage failed; checkpoint retained, retry after checking store/CLI availability.') from None
