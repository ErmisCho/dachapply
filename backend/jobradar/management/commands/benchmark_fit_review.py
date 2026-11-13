"""TASK-368: pair measured runs for private owner review; no database/provider access."""
import json

from django.core.management.base import BaseCommand, CommandError

from jobradar.services.benchmark import outside_repo
from jobradar.services.benchmark_fit_requirements import write_review


class Command(BaseCommand):  # TASK-368
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument('--separate', required=True)
        parser.add_argument('--combined', required=True)
        parser.add_argument('--out', required=True)

    def handle(self, *args, **options):
        output = outside_repo(options['out'])
        if output.exists():
            raise CommandError('Output already exists; choose a fresh directory.')
        results = [json.loads((outside_repo(options[v]) / 'results.json').read_text(encoding='utf-8')) for v in ('separate', 'combined')]
        if [r['variant'] for r in results] != ['separate', 'combined']:
            raise CommandError('Pass the corresponding separate and combined result directories.')
        output.mkdir(parents=True)
        write_review(results, output)
        self.stdout.write(f'Owner review written to {output / "review.md"}')
