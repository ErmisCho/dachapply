from django.core.management.base import BaseCommand

from jobradar.services.mailbox import backfill_message_bodies


class Command(BaseCommand):
    help = (
        'TASK-132 AC3/AC4: fill body_text for existing MailboxMessage rows via their own stored '
        'gmail_id -- the 648 rows logged before body_text existed. Resumable and idempotent: each '
        'call only ever selects rows still empty, so an interrupted run can simply be re-run. --limit '
        'bounds how many rows one call attempts (default: services.mailbox.BACKFILL_BATCH_LIMIT). '
        'Needs the Gmail API (OAuth) transport; IMAP-sourced rows have no gmail_id to refetch by. Dry '
        'run by default; --yes actually writes.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--yes', action='store_true', help='Actually write the fetched bodies. Without it the command only reports what it would fill.')
        parser.add_argument('--limit', type=int, default=None, help='Cap how many empty-body rows this call attempts (default: services.mailbox.BACKFILL_BATCH_LIMIT).')

    def handle(self, *args, **opts):
        result = backfill_message_bodies(dry_run=not opts['yes'], limit=opts['limit'])
        if result['refused']:
            self.stdout.write(self.style.ERROR(result['refused']))
            return

        self.stdout.write(
            f"Attempted {result['attempted']} row(s): {result['filled']} {'filled' if opts['yes'] else 'would be filled'}, "
            f"{result['failed']} failed or came back empty, {result['skipped_no_gmail_id']} row(s) have no gmail_id at all "
            'and cannot be backfilled this way.'
        )
        if opts['yes']:
            self.stdout.write(self.style.SUCCESS(f"Filled {result['filled']} message body/bodies."))
        else:
            self.stdout.write(self.style.WARNING('Dry run: nothing was written. Re-run with --yes to write.'))
