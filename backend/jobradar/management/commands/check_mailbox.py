from django.core.management.base import BaseCommand
from django.utils import timezone

from jobradar.services.mailbox import MailboxCheckInProgress, pending_mailbox_check_request, run_check, seed_fake_run


class Command(BaseCommand):
    help = (
        'TASK-109/TASK-110: check the owner Gmail mailbox (IMAP app password, or Gmail-API OAuth via '
        '`manage.py gmail_oauth_setup` for an owner who has declined 2-Step Verification -- plus '
        'calendar-aware quiet hours, all from the local .env) for new job-search email, produce '
        'reviewable pipeline suggestions, and draft guarded replies into Gmail Drafts for '
        'reply-wanting messages. Intended to be invoked by Windows Task Scheduler (or a developer) '
        'roughly hourly; the command itself enforces the configured cadence, so a more frequent '
        'scheduler trigger is harmless. The app only ever appends drafts -- sending is exclusively '
        'the owner in Gmail.\n\n'
        'TASK-124 AC3: before its own cadence-gated tick, this command first looks for a mailbox '
        'check request recorded from a backend with no mail credentials (the deployed site) and, if '
        'one is pending, runs that instead -- regardless of whether the cadence is due -- and marks '
        'it handled so it only ever runs once.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true', help='Ignore the cadence setting and run immediately (calendar quiet-hours still applies).')
        parser.add_argument('--seed-fake', action='store_true', help='Skip IMAP and the calendar entirely; insert one fixture run with a pending suggestion, for manually testing the review UI.')

    def handle(self, *args, **opts):
        if opts['seed_fake']:
            run = seed_fake_run()
            self.stdout.write(self.style.SUCCESS(
                f'Seeded fake mailbox run #{run.id} with {run.suggestion_count} suggestion(s), '
                f'{run.draft_written_count} draft(s) ready, and {run.draft_blocked_count} draft(s) blocked, and {run.suggestion_blocked_count} suggestion(s) refused as bulk mail. '
                'Review it at /mailbox in the app.'
            ))
            return

        pending_request = pending_mailbox_check_request()
        if pending_request is not None:
            try:
                run = run_check(force=True)
            except MailboxCheckInProgress as exc:
                # Left unhandled on purpose: a check already in flight means this request will get
                # picked up on a later tick instead, not lost.
                self.stdout.write(self.style.WARNING(f'A mailbox check request is queued, but {exc} Will retry on the next tick.'))
                return
            pending_request.handled_at = timezone.now()
            pending_request.result_run = run
            pending_request.save(update_fields=['handled_at', 'result_run'])
            self.stdout.write(f'Handled queued check request #{pending_request.id}.')
            self._report(run)
            return

        try:
            run = run_check(force=opts['force'])
        except MailboxCheckInProgress as exc:
            self.stdout.write(self.style.WARNING(str(exc)))
            return
        if run is None:
            self.stdout.write('Not due yet (or neither GMAIL_IMAP_USER/APP_PASSWORD nor GMAIL_OAUTH_CLIENT_ID/SECRET, nor the owner account, are configured).')
            return
        self._report(run)

    def _report(self, run):
        if run is None:
            self.stdout.write('Mailbox check did not run: no owner account is configured for this backend.')
        elif run.skipped:
            self.stdout.write(self.style.WARNING(f'Skipped: {run.skip_reason}.'))
        elif run.error:
            self.stdout.write(self.style.ERROR(f'Mailbox check failed: {run.error}'))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'Checked mailbox: {run.fetched_count} fetched, {run.job_related_count} job-related, '
                f'{run.uncertain_count} uncertain, {run.suggestion_count} suggestion(s), '
                f'{run.draft_written_count} draft(s) ready, {run.draft_blocked_count} draft(s) blocked, {run.suggestion_blocked_count} suggestion(s) refused as bulk mail.'
            ))
            if run.drafting_skipped:
                # Say it out loud: without this line a first run reports job-related mail and zero
                # drafts, which reads as a broken drafting path rather than the deliberate baseline.
                self.stdout.write(self.style.WARNING(
                    'This was a first run with no prior history, so reply drafting was skipped -- '
                    'otherwise it would have drafted replies to your entire mailbox. Messages and '
                    'suggestions above are recorded as normal; drafting starts from the next run.'
                ))
