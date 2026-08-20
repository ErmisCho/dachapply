import sys

from django.core.management.base import BaseCommand

from jobradar.services.mailbox import detach_job_board_messages


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
        'TASK-129: clear matched_job on MailboxMessage rows whose SENDER is a job board '
        '(services.mailbox.is_job_board(), the TASK-114 predicate -- no second list) -- the false '
        'association TASK-114 stopped happening going forward but never cleaned up historically. Rows '
        'are never deleted (TASK-109 AC5 append-only log survives); only the wrong matched_job is '
        'cleared, and any still-pending MailboxSuggestion derived from one of those messages is '
        'dismissed with it. Dry run by default; --yes actually writes.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--yes', action='store_true', help='Actually clear matched_job and dismiss suggestions. Without it the command only reports what it would do.')

    def handle(self, *args, **opts):
        results = detach_job_board_messages(dry_run=not opts['yes'])
        if not results:
            self.stdout.write('No job-board sender is matched to a job. Nothing to do.')
            return

        total_messages = 0
        total_dismissed = 0
        for row in results:
            job = row['job']
            total_messages += row['message_count']
            total_dismissed += row['dismissed_count']
            self.stdout.write(_console_safe(
                f"  job {job.id} ({job.company} -- {job.title}): "
                f"{row['message_count']} message(s), {row['dismissed_count']} pending suggestion(s)"
            ))

        if opts['yes']:
            self.stdout.write(self.style.SUCCESS(
                f"Detached {total_messages} message(s) across {len(results)} job(s); "
                f"dismissed {total_dismissed} pending suggestion(s)."
            ))
        else:
            self.stdout.write(self.style.WARNING(
                f"Dry run: {total_messages} message(s) across {len(results)} job(s) would be detached "
                f"({total_dismissed} pending suggestion(s) would be dismissed). Re-run with --yes to act."
            ))
