import sys

from django.core.management.base import BaseCommand

from jobradar.models import JobLead
from jobradar.services.cv_generator import latest_generated_sources
from jobradar.services.cv_tasks import READY_TO_SUBMIT_FROM, mark_ready_to_submit


def _console_safe(text):
    # Company/title come straight from postings; see dedupe_pending_suggestions.py for the cp1252 crash.
    encoding = getattr(sys.stdout, 'encoding', '') or 'utf-8'
    return text.encode(encoding, 'replace').decode(encoding, 'replace')


class Command(BaseCommand):
    help = (
        "TASK-265 AC3: move unapplied jobs (new/reviewed/to_apply) that already have a generated CV "
        "and/or letter on disk to 'ready_to_submit'. Files are looked up read-only per the job's "
        "submitted_for user, then its created_by user. Dry run by default; --apply writes."
    )

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Actually change the statuses. Without it the command only reports.')

    def handle(self, *args, **opts):
        found = []
        jobs = JobLead.objects.filter(status__in=READY_TO_SUBMIT_FROM).select_related('submitted_for', 'created_by').order_by('id')
        for job in jobs:
            for user in dict.fromkeys(u for u in (job.submitted_for, job.created_by) if u):
                cv, letter = latest_generated_sources(job, user)
                if cv or letter:
                    found.append((job, cv, letter))
                    break
        for job, cv, letter in found:
            self.stdout.write(_console_safe(
                f'  job {job.id} ({job.company} -- {job.title}) status={job.status} cv={cv or "-"} letter={letter or "-"}'))
        if not opts['apply']:
            self.stdout.write(self.style.WARNING(
                f'Dry run: {len(found)} job(s) would move to ready_to_submit. Re-run with --apply to write.'))
            return
        changed = sum(mark_ready_to_submit(job.id) for job, _cv, _letter in found)
        self.stdout.write(self.style.SUCCESS(f'Moved {changed} of {len(found)} job(s) to ready_to_submit.'))
