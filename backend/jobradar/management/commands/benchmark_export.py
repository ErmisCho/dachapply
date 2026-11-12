"""TASK-370: read-only private benchmark fixture export."""
from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ObjectDoesNotExist
from jobradar.services.benchmark import export_fixture


class Command(BaseCommand):
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument('--email', required=True)
        parser.add_argument('--jobs', required=True, help='N most recent New/To apply jobs, comma IDs, or ids:ID')
        parser.add_argument('--out', required=True)

    def handle(self, *args, **options):
        try:
            count = export_fixture(options['email'], options['jobs'], options['out'])
        except (ValueError, LookupError, ObjectDoesNotExist):
            raise CommandError('Invalid owner or job selection.') from None
        self.stdout.write(f"Exported {count} jobs to {options['out']}")
