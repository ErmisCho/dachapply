import sys

from django.core.management.base import BaseCommand
from django.utils import timezone

from jobradar.services.mailbox import backfill_interview_dates, interview_date_coverage


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
        'TASK-179 AC4/AC5: fill JobLead.interview_at from the interview date already sitting in the '
        "job's own matched mail -- an attached iCalendar VEVENT (MailboxMessage.calendar_start, "
        'parsed since TASK-135) or a readable time in an interview_invitation body. Measured '
        '2026-08-23: interview_at was populated on 0 of the 82 tracked jobs, so the board\'s Upcoming '
        'interviews panel could never render a row. Never overwrites a date a human already set, '
        'never changes a status, never a migration. Dry run by default; --yes actually writes. Prints '
        'the AC5 census before (and, with --yes, after) either way -- run it once before and once '
        'after to get the before/after numbers.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--yes', action='store_true', help='Actually write interview_at. Without it the command only reports what it would do.')

    def _census(self, label):
        counts = interview_date_coverage()
        self.stdout.write(f'{label} (owner: {counts["owner"] or "NOT CONFIGURED -- set CODEX_CV_OWNER_EMAIL"})')
        self.stdout.write(f'  jobs                                     {counts["jobs"]}')
        self.stdout.write(f'  jobs with interview_at                   {counts["jobs_with_interview_at"]}')
        self.stdout.write(f'  jobs in interview status                 {counts["jobs_in_interview_status"]}')
        self.stdout.write(f'  Upcoming interviews panel rows           {counts["upcoming_interviews"]} (the panel renders at most 10)')
        self.stdout.write(f'  interview_date suggestions               {counts["interview_date_suggestions"]} '
                          f'({counts["interview_date_suggestions_pending"]} pending, {counts["interview_date_suggestions_confirmed"]} confirmed, '
                          f'{counts["interview_date_suggestions_carrying_a_date"]} carrying a date)')
        self.stdout.write(f'  messages classified interview_invitation {counts["messages_classified_interview_invitation"]}')
        self.stdout.write(f'  messages carrying a calendar_start       {counts["messages_with_calendar_start"]} '
                          f'({counts["messages_with_calendar_start_not_classified_invitation"]} of them NOT classified as an invitation)')
        return counts

    def handle(self, *args, **opts):
        self._census('Before:')
        results = backfill_interview_dates(dry_run=not opts['yes'])
        if not results:
            self.stdout.write('\nNo job is missing an interview_at that its own matched mail can supply. Nothing to do.')
            return

        now = timezone.now()
        self.stdout.write(f'\n{len(results)} job(s) with a date in their mail:')
        for row in results:
            job, message, when = row['job'], row['message'], row['interview_at']
            past = '' if when >= now else '  [already past -- recorded, but the panel only shows future dates]'
            self.stdout.write(_console_safe(
                f'  job {job.id} ({job.company} -- {job.title}, status {job.status}): '
                f'{timezone.localtime(when).strftime("%d.%m.%Y %H:%M")} from the {row["source"]} of message {message.pk} '
                f'({message.sender}, "{message.subject[:60]}", classified {message.classification}){past}'
            ))

        if opts['yes']:
            self.stdout.write(self.style.SUCCESS(f'\nWrote interview_at on {len(results)} job(s).'))
            self._census('\nAfter:')
        else:
            self.stdout.write(self.style.WARNING(
                f'\nDry run: interview_at would be written on {len(results)} job(s). Re-run with --yes to act.'
            ))
