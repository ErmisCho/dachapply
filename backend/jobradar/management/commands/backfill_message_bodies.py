from django.core.management.base import BaseCommand

from jobradar.services.mailbox import backfill_message_bodies


class Command(BaseCommand):
    help = (
        'TASK-132 AC3/AC4: fill body_text for existing MailboxMessage rows via their own stored '
        'gmail_id -- the 648 rows logged before body_text existed. Resumable and idempotent: each '
        'call only ever selects rows still empty, so an interrupted run can simply be re-run. --limit '
        'bounds how many rows one call attempts (default: services.mailbox.BACKFILL_BATCH_LIMIT). '
        'Needs the Gmail API (OAuth) transport; IMAP-sourced rows have no gmail_id to refetch by. Dry '
        'run by default; --yes actually writes. TASK-150: --calendar-missing switches to a second, '
        'disjoint mode -- rows that already have a body (filled by this command before calendar '
        'support existed) but still have empty calendar_summary/location/organizer/start/end are '
        'refetched and gain ONLY calendar fields (and attachments); body_text is never touched in '
        'this mode. A row confirmed to genuinely carry no calendar data is not re-attempted on later '
        'calls (see services.mailbox.backfill_message_bodies docstring for the calendar_checked_at '
        'discriminator).'
    )

    def add_arguments(self, parser):
        parser.add_argument('--yes', action='store_true', help='Actually write the fetched bodies/calendar fields. Without it the command only reports what it would fill.')
        parser.add_argument('--limit', type=int, default=None, help='Cap how many candidate rows this call attempts (default: services.mailbox.BACKFILL_BATCH_LIMIT).')
        parser.add_argument('--calendar-missing', action='store_true', help='Backfill calendar fields only, on rows that already have a body_text. Never writes body_text.')

    def handle(self, *args, **opts):
        calendar_missing = opts['calendar_missing']
        result = backfill_message_bodies(dry_run=not opts['yes'], limit=opts['limit'], calendar_missing=calendar_missing)
        if result['refused']:
            self.stdout.write(self.style.ERROR(result['refused']))
            return

        what = 'calendar field set' if calendar_missing else 'body/bodies'
        fail_note = 'failed, came back empty, or genuinely have no calendar data' if calendar_missing else 'failed or came back empty'
        self.stdout.write(
            f"Attempted {result['attempted']} row(s): {result['filled']} {'filled' if opts['yes'] else 'would be filled'}, "
            f"{result['failed']} {fail_note}, {result['skipped_no_gmail_id']} row(s) have no gmail_id at all "
            'and cannot be backfilled this way.'
        )
        if opts['yes']:
            self.stdout.write(self.style.SUCCESS(f"Filled {result['filled']} message {what}."))
        else:
            self.stdout.write(self.style.WARNING('Dry run: nothing was written. Re-run with --yes to write.'))
