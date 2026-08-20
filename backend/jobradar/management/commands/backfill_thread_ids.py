from django.core.management.base import BaseCommand

from jobradar.services.mailbox import backfill_thread_ids


class Command(BaseCommand):
    help = (
        'TASK-132 AC1: fill thread_id for existing MailboxMessage rows via their own stored gmail_id, '
        'so ingest_threads has threads to expand. Only rows written since TASK-121 carry one (5 of 653 '
        'on the owner mailbox when this was written), and without a thread_id a conversation can never '
        'be more than the inbox fragments already logged. Uses format=minimal -- one field per message, '
        'not a full re-download. Resumable and idempotent: each call only selects rows still missing a '
        'thread_id, so an interrupted run can simply be re-run. Dry run by default; --yes actually writes.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--yes', action='store_true', help='Actually write the thread ids. Without it the command only reports what it would fill.')
        parser.add_argument('--limit', type=int, default=None, help='Cap how many rows this call attempts (default: services.mailbox.BACKFILL_BATCH_LIMIT).')

    def handle(self, *args, **opts):
        result = backfill_thread_ids(dry_run=not opts['yes'], limit=opts['limit'])
        if result['refused']:
            self.stdout.write(self.style.ERROR(result['refused']))
            return

        self.stdout.write(
            f"Attempted {result['attempted']} row(s): {result['filled']} {'filled' if opts['yes'] else 'would be filled'}, "
            f"{result['failed']} failed or came back without a threadId, {result['skipped_no_gmail_id']} row(s) have no "
            'gmail_id at all and cannot be backfilled this way.'
        )
        if opts['yes']:
            self.stdout.write(self.style.SUCCESS(f"Filled {result['filled']} thread id(s)."))
        else:
            self.stdout.write(self.style.WARNING('Dry run: nothing was written. Re-run with --yes to write.'))
