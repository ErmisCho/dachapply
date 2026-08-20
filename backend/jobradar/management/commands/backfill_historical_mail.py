from django.core.management.base import BaseCommand

from jobradar.services.mailbox import BACKFILL_HISTORICAL_LIMIT_DEFAULT, FETCH_HISTORY_FLOOR_DAYS, backfill_historical_mail


class Command(BaseCommand):
    help = (
        'TASK-136 AC1: a ONE-OFF, marker-IGNORING backward re-fetch. run_check()/fetch_new() only ever '
        'read FORWARD from the resume marker (MAX(internal_date_ms)) once one exists, so a message '
        'OLDER than that marker -- an application confirmation archived months before the mailbox '
        'check first ran, for instance -- is permanently unreachable by any number of normal runs, '
        'however wide fetch_new()\'s own label filter is. This command lists Gmail by date floor '
        '(FETCH_HISTORY_FLOOR_DAYS, override with --floor-days) instead of the marker. Owner decision '
        '2026-08-19: TARGETED by default -- from:(tracked-job domains) OR subject:(application-'
        'confirmation phrases), not a bare date floor -- a dry run against the real mailbox found '
        '~3,411 new messages (the whole two-year mailbox, almost all not_job_related) before this '
        'shipped; --all-mail restores the old bare-floor behaviour, opt-in only. Classifies and '
        'matches what it finds exactly as a live run would (so an application confirmation lands as '
        'application_confirmed, not not_job_related), and never drafts a reply -- these are years-old '
        'messages, not mail a live run just fetched. Resumable and idempotent: dedupes on gmail_id, so '
        'an interrupted run can simply be re-run. Dry run by default; --yes actually writes.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--yes', action='store_true', help='Actually create the rows. Without it the command only reports what it would create.')
        parser.add_argument('--limit', type=int, default=None, help=f'Cap how many NEW messages this call fetches in full and creates (default: {BACKFILL_HISTORICAL_LIMIT_DEFAULT}).')
        parser.add_argument('--floor-days', type=int, default=None, help=f'How many days back to list from, ignoring the resume marker (default: {FETCH_HISTORY_FLOOR_DAYS}).')
        parser.add_argument('--all-mail', action='store_true', help='Drop the tracked-job-domain/application-confirmation-phrase filter and list EVERYTHING since the floor. Not the default -- this is the whole mailbox, bodies included.')

    def handle(self, *args, **opts):
        result = backfill_historical_mail(dry_run=not opts['yes'], limit=opts['limit'], floor_days=opts['floor_days'], all_mail=opts['all_mail'])
        if result['refused']:
            self.stdout.write(self.style.ERROR(result['refused']))
            return

        batched_note = ' (tracked-job domains were too many for one query and had to be split)' if result['batched'] else ''
        self.stdout.write(f"Query matched {result['matched_by_query']} message(s){batched_note}.")
        self.stdout.write(
            f"{result['already_present']} already stored. "
            f"Attempted {result['attempted']} new message(s): {result['created']} {'created' if opts['yes'] else 'would be created'}, "
            f"{result['skipped_by_bound']} left for a later call (--limit)."
        )
        if opts['yes']:
            self.stdout.write(self.style.SUCCESS(f"Created {result['created']} message(s)."))
        else:
            self.stdout.write(self.style.WARNING('Dry run: nothing was written. Re-run with --yes to write.'))
