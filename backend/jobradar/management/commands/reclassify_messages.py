import sys

from django.core.management.base import BaseCommand

from jobradar.services.mailbox import reclassify_messages


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
        'TASK-162 AC6 / TASK-168 AC6: re-run classification over MailboxMessage rows already stored '
        'as rejection/interview_invitation/offer/application_confirmed. A heuristic-evaluated row is '
        're-run through the full classifier (TASK-168: may change which of the four it lands in, not '
        'just whether one is allowed at all); an LLM-evaluated row only has the false-positive guard '
        '(services.mailbox._guard_status_changing -- Rule A, platform senders; Rule B, no '
        'application-context evidence) re-applied. A confirmed decision is never touched, and a still-'
        'pending suggestion generated from a changed row is dismissed with it. Dry run by default; '
        '--yes actually writes.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--yes', action='store_true', help='Actually write the reclassification and dismiss affected pending suggestions. Without it the command only reports what it would do.')
        parser.add_argument('--limit', type=int, default=None, help='Cap how many status-changing rows this call inspects (default: no cap).')

    def handle(self, *args, **opts):
        changes = reclassify_messages(dry_run=not opts['yes'], limit=opts['limit'])
        if not changes:
            self.stdout.write('No stored classification is blocked by the new guard. Nothing to do.')
            return

        total_dismissed = 0
        for row in changes:
            message = row['message']
            total_dismissed += row['dismissed_count']
            self.stdout.write(_console_safe(
                f"  message {message.pk} ({message.sender}: {message.subject[:60]!r}): "
                f"{row['from']} -> {row['to']} ({row['dismissed_count']} pending suggestion(s))"
            ))

        if opts['yes']:
            self.stdout.write(self.style.SUCCESS(
                f"Reclassified {len(changes)} message(s); dismissed {total_dismissed} pending suggestion(s)."
            ))
        else:
            self.stdout.write(self.style.WARNING(
                f"Dry run: {len(changes)} message(s) would be reclassified "
                f"({total_dismissed} pending suggestion(s) would be dismissed). Re-run with --yes to write."
            ))
