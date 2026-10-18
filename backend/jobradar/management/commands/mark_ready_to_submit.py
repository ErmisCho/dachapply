import sys

from django.core.management.base import BaseCommand

from jobradar.services.cv_generator import latest_generated_sources
from jobradar.services.cv_tasks import has_prepared_drafts, mark_ready_to_submit, promotable_jobs


def _console_safe(text):
    # Company/title come straight from postings; see dedupe_pending_suggestions.py for the cp1252 crash.
    encoding = getattr(sys.stdout, 'encoding', '') or 'utf-8'
    return text.encode(encoding, 'replace').decode(encoding, 'replace')


class Command(BaseCommand):
    help = (
        "TASK-265 AC3: move unapplied jobs (new/reviewed/to_apply) that already have a generated CV "
        "and/or letter on disk to 'ready_to_submit', unless their latest evaluation recommends 'skip' "
        "(TASK-310). Files are looked up read-only per the job's submitted_for user, then its "
        "created_by user. Dry run by default; --apply writes."
    )

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Actually change the statuses. Without it the command only reports.')

    def handle(self, *args, **opts):
        found = []
        # TASK-310: the same queryset mark_ready_to_submit updates, so the dry run lists no 'skip' job.
        jobs = promotable_jobs().select_related('submitted_for', 'created_by').order_by('id')
        for job in jobs:
            for user in dict.fromkeys(u for u in (job.submitted_for, job.created_by) if u):
                cv, letter = latest_generated_sources(job, user)
                # TASK-280.3: prepared drafts wait for the owner's package selection.
                if (cv or letter) and not has_prepared_drafts(job.id, user.pk):
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
