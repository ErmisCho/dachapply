import sys

from django.core.management.base import BaseCommand, CommandError

from jobradar.services.mailbox import GmailApiTransport, _default_transport, purge_app_drafts


def _console_safe(text: str) -> str:
    """Subject lines are real mail: emoji and umlauts both turn up (a devjobs.at blast crashed this
    command on a cp1252 Windows console mid-listing). Only characters the actual console cannot
    encode are replaced, so a UTF-8 terminal still prints them intact.
    """
    encoding = getattr(sys.stdout, 'encoding', '') or 'utf-8'
    return text.encode(encoding, 'replace').decode(encoding, 'replace')


class Command(BaseCommand):
    help = (
        'TASK-114 AC6: delete the reply drafts THIS APP wrote from the Gmail Drafts folder -- the '
        'ones drafted at job-board newsletters, and the cold-start batch drafted at long-dead '
        'application threads (TASK-110). A draft is matched only when its body is byte-for-byte (up '
        'to whitespace) a draft the MailboxDraft log records writing, so a hand-written draft can '
        'never be caught. Dry run by default; --yes actually deletes, and Gmail draft deletion is '
        'permanent -- deleted drafts do not go to Trash.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--yes', action='store_true', help='Actually delete. Without it the command only lists what it would delete.')

    def handle(self, *args, **opts):
        transport = _default_transport()
        # ponytail: OAuth only. IMAP draft deletion (STORE \Deleted + EXPUNGE on [Gmail]/Drafts) is
        # not implemented -- the owner's account runs on OAuth; add it if an IMAP-configured machine
        # ever needs the same undo.
        if not isinstance(transport, GmailApiTransport):
            raise CommandError('Draft purging needs the Gmail API (OAuth) transport; IMAP is not supported.')

        removed = purge_app_drafts(transport, dry_run=not opts['yes'])
        if not removed:
            self.stdout.write('No drafts in Gmail match anything this app recorded writing. Nothing to do.')
            return
        for draft_id, subject in removed:
            self.stdout.write(_console_safe(f'  {draft_id}  {subject}'))
        if opts['yes']:
            self.stdout.write(self.style.SUCCESS(f'Deleted {len(removed)} draft(s) from Gmail Drafts.'))
        else:
            self.stdout.write(self.style.WARNING(f'Dry run: {len(removed)} draft(s) would be deleted. Re-run with --yes to delete them.'))
