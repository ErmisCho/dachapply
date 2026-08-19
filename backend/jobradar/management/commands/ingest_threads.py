from django.core.management.base import BaseCommand

from jobradar.services.mailbox import ingest_threads


class Command(BaseCommand):
    help = (
        'TASK-132 AC1/AC5: ingest the whole Gmail thread of every matched-job message -- including '
        'what the OWNER sent, which the normal mailbox check never reads (it only ever queries the '
        'INBOX label). Bounded on purpose: matched-jobs-only threads, a per-thread message cap, and '
        '(via --limit) how many threads one call processes -- see services.mailbox.ingest_threads for '
        'the exact numbers. Needs the Gmail API (OAuth) transport; IMAP has no thread concept. Dry '
        'run by default; --yes actually writes.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--yes', action='store_true', help='Actually create the rows. Without it the command only reports what it would create.')
        parser.add_argument('--limit', type=int, default=None, help='Cap how many threads this call processes (default: services.mailbox.INGEST_THREAD_LIMIT_DEFAULT).')

    def handle(self, *args, **opts):
        result = ingest_threads(dry_run=not opts['yes'], limit=opts['limit'])
        if result['refused']:
            self.stdout.write(self.style.ERROR(result['refused']))
            return

        self.stdout.write(
            f"Threads: {result['threads_attempted']} attempted, {result['threads_failed']} failed to read, "
            f"{result['threads_skipped_capped']} left for a later run (thread-count cap)."
        )
        self.stdout.write(
            f"Messages: {result['messages_created']} {'created' if opts['yes'] else 'would be created'}, "
            f"{result['messages_skipped_existing']} already stored, "
            f"{result['messages_skipped_thread_cap']} skipped (per-thread message cap)."
        )
        if opts['yes']:
            self.stdout.write(self.style.SUCCESS(f"Ingested {result['messages_created']} message(s)."))
        else:
            self.stdout.write(self.style.WARNING('Dry run: nothing was written. Re-run with --yes to write.'))
