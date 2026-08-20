import sys

from django.core.management.base import BaseCommand

from jobradar.services.mailbox import rematch_ats_display_name_messages


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
        'TASK-140 AC5: back-catalogue pass -- every already-stored MailboxMessage with matched_job '
        'still NULL, whose sender is a known multi-tenant applicant-tracking-system host '
        '(services.mailbox.is_ats_host(), the TASK-137 AC2 predicate -- no second list), is matched '
        'by the company name in its From DISPLAY NAME (services.mailbox._match_by_ats_display_name, '
        'the same token-subset rule the live matching path (match_job) now applies -- no second '
        'rule). Only ever fills in a currently-empty match; a row that already carries a matched_job '
        '(live-matched or attached by hand) is never touched, and no message is ever deleted. Dry run '
        'by default; --yes actually writes matched_job.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--yes', action='store_true', help='Actually set matched_job on the matched rows. Without it the command only reports what it would do.')

    def handle(self, *args, **opts):
        results = rematch_ats_display_name_messages(dry_run=not opts['yes'])
        if not results:
            self.stdout.write('No ATS-host message with a NULL matched_job matches a tracked company by display name. Nothing to do.')
            return

        total_messages = 0
        for row in results:
            job = row['job']
            total_messages += row['message_count']
            self.stdout.write(_console_safe(f"  job {job.id} ({job.company} -- {job.title}): {row['message_count']} message(s)"))
            for message in row['messages']:
                self.stdout.write(_console_safe(f"    - uid {message.uid}: {message.sender} -- {message.subject}"))

        if opts['yes']:
            self.stdout.write(self.style.SUCCESS(f"Attached {total_messages} message(s) across {len(results)} job(s)."))
        else:
            self.stdout.write(self.style.WARNING(f"Dry run: {total_messages} message(s) across {len(results)} job(s) would be attached. Re-run with --yes to act."))
