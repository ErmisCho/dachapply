"""TASK-370: scratch-only benchmark runner."""
from django.core.management.base import BaseCommand
from jobradar.services.benchmark import EXPERIMENTS, run_fixture


class Command(BaseCommand):
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument('--fixture', required=True)
        parser.add_argument('--experiment', required=True, choices=EXPERIMENTS)
        parser.add_argument('--variant')
        parser.add_argument('--workers', type=int, default=1)
        parser.add_argument('--out', required=True)

    def handle(self, *args, **options):
        result = run_fixture(options['fixture'], options['experiment'], options['variant'], options['workers'], options['out'])
        self.stdout.write(f"Recorded {len(result['artifacts'])} artifacts in {options['out']}")
