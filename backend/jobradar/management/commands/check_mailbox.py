from django.core.management.base import BaseCommand

from jobradar.services.mailbox import run_check, seed_fake_run


class Command(BaseCommand):
    help = (
        'TASK-109/TASK-110: check the owner Gmail mailbox (IMAP app password + calendar-aware quiet '
        'hours, both from the local .env) for new job-search email, produce reviewable pipeline '
        'suggestions, and draft guarded replies into Gmail Drafts for reply-wanting messages. '
        'Intended to be invoked by Windows Task Scheduler (or a developer) roughly hourly; the '
        'command itself enforces the configured cadence, so a more frequent scheduler trigger is '
        'harmless. The app only ever appends drafts -- sending is exclusively the owner in Gmail.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true', help='Ignore the cadence setting and run immediately (calendar quiet-hours still applies).')
        parser.add_argument('--seed-fake', action='store_true', help='Skip IMAP and the calendar entirely; insert one fixture run with a pending suggestion, for manually testing the review UI.')

    def handle(self, *args, **opts):
        if opts['seed_fake']:
            run = seed_fake_run()
            self.stdout.write(self.style.SUCCESS(
                f'Seeded fake mailbox run #{run.id} with {run.suggestion_count} suggestion(s), '
                f'{run.draft_written_count} draft(s) ready, and {run.draft_blocked_count} draft(s) blocked. '
                'Review it at /mailbox in the app.'
            ))
            return

        run = run_check(force=opts['force'])
        if run is None:
            self.stdout.write('Not due yet (or GMAIL_IMAP_USER/APP_PASSWORD/owner account are not configured).')
        elif run.skipped:
            self.stdout.write(self.style.WARNING(f'Skipped: {run.skip_reason}.'))
        elif run.error:
            self.stdout.write(self.style.ERROR(f'Mailbox check failed: {run.error}'))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'Checked mailbox: {run.fetched_count} fetched, {run.job_related_count} job-related, '
                f'{run.uncertain_count} uncertain, {run.suggestion_count} suggestion(s), '
                f'{run.draft_written_count} draft(s) ready, {run.draft_blocked_count} draft(s) blocked.'
            ))
