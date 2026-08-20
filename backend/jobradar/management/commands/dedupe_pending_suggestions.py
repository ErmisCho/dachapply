import sys

from django.core.management.base import BaseCommand

from jobradar.services.mailbox import dismiss_redundant_pending_suggestions


def _console_safe(text: str) -> str:
    """Company/title strings come straight from job postings: emoji and umlauts both turn up (see
    purge_app_drafts.py, which hit a cp1252 Windows console crash on a subject line for the same
    reason). Only characters the actual console cannot encode are replaced, so a UTF-8 terminal still
    prints them intact.
    """
    encoding = getattr(sys.stdout, 'encoding', '') or 'utf-8'
    return text.encode(encoding, 'replace').decode(encoding, 'replace')


class Command(BaseCommand):
    help = (
        'TASK-130 AC2: dismiss the redundant PENDING MailboxSuggestion duplicates build_suggestions() '
        'created before it had its own one-pending-per-(job, suggestion_type) guard -- three identical '
        'pending feedback_clear rows on one job, measured in production. Keeps the oldest row per '
        '(job, suggestion_type) group (the survivor carries the same payload every duplicate does, so '
        'nothing is lost) and dismisses the rest. Never touches Gmail -- the three duplicate drafts '
        'already written there are purge_app_drafts\' job, not this command\'s. Dry run by default; '
        '--yes actually dismisses.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--yes', action='store_true', help='Actually dismiss the duplicates. Without it the command only reports what it would do.')

    def handle(self, *args, **opts):
        results = dismiss_redundant_pending_suggestions(dry_run=not opts['yes'])
        if not results:
            self.stdout.write('No job has more than one pending suggestion of the same type. Nothing to do.')
            return

        total_dismissed = 0
        for row in results:
            job = row['job']
            total_dismissed += row['dismissed_count']
            self.stdout.write(_console_safe(
                f"  job {job.id} ({job.company} -- {job.title}) {row['suggestion_type']}: "
                f"keeping suggestion {row['kept_id']}, dismissing {row['dismissed_count']} duplicate(s)"
            ))

        if opts['yes']:
            self.stdout.write(self.style.SUCCESS(
                f"Dismissed {total_dismissed} duplicate pending suggestion(s) across {len(results)} (job, type) group(s)."
            ))
        else:
            self.stdout.write(self.style.WARNING(
                f"Dry run: {total_dismissed} duplicate pending suggestion(s) across {len(results)} (job, type) group(s) "
                f"would be dismissed. Re-run with --yes to act."
            ))
