from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from jobradar.models import ApplicationNote, JobLead, MailboxMessage, MailboxRun, MailboxSuggestion
from jobradar.services.mailbox import _owner_user

# Every row this command creates carries this company name, and --delete removes rows matching it and
# nothing else. Deliberately not an id passed on the command line: the delete side must be unable to
# reach a real job even if it is run with the wrong arguments, on the wrong database, twice.
FIXTURE_COMPANY = 'ZZ TASK-175 browser fixture'
# MailboxMessage.uid is globally unique with no user FK, so the fixture needs one that cannot collide
# with a real Gmail-API row. Those are a locally-assigned sequence in processing order (see that
# model's docstring) and production's highest is in the low thousands; this sits far above it.
FIXTURE_UID = 917_500_175


class Command(BaseCommand):
    help = (
        'TASK-175 AC8: create (or delete) ONE synthetic job + mail + pending rejection suggestion so the '
        'postpone control can be driven end to end in a browser. Needed because production currently has '
        '0 pending suggestions on actionable jobs, so the "Email decisions" panel renders no card at all. '
        'Everything it makes is named "%s" and --delete removes exactly that. Safe to run twice; creates '
        'nothing on --delete and deletes nothing on --create.' % FIXTURE_COMPANY
    )

    def add_arguments(self, parser):
        parser.add_argument('--create', action='store_true', help='Create the fixture job, message and pending suggestion.')
        parser.add_argument('--delete', action='store_true', help='Delete every row this command created (matched on the fixture company name).')
        parser.add_argument('--due-in-days', type=int, default=None, help='With --create: also set the job feedback_due_date this many days from today (negative = already overdue), to check the resurfacing half of AC5 without waiting.')

    def handle(self, *args, **options):
        if options['create'] == options['delete']:
            raise CommandError('Pass exactly one of --create or --delete.')
        if options['delete']:
            return self._delete()
        return self._create(options['due_in_days'])

    def _delete(self):
        jobs = JobLead.objects.filter(company=FIXTURE_COMPANY)
        if not jobs.exists():
            self.stdout.write('Nothing to delete: no job named "%s".' % FIXTURE_COMPANY)
            return
        # MailboxMessage.matched_job is on_delete=SET_NULL, so the message would survive the job and
        # keep showing up in the unmatched list. Delete it explicitly, by uid, first.
        messages = MailboxMessage.objects.filter(uid=FIXTURE_UID)
        runs = MailboxRun.objects.filter(messages__uid=FIXTURE_UID).distinct()
        counts = {
            'suggestions': MailboxSuggestion.objects.filter(job__in=jobs).count(),
            'notes': ApplicationNote.objects.filter(job__in=jobs).count(),
            'messages': messages.count(),
            'runs': runs.count(),
            'jobs': jobs.count(),
        }
        messages.delete()
        runs.delete()
        jobs.delete()  # cascades to its suggestions and notes
        self.stdout.write('Deleted %(jobs)d job, %(messages)d message, %(runs)d run, %(suggestions)d suggestion, %(notes)d note.' % counts)

    def _create(self, due_in_days):
        if JobLead.objects.filter(company=FIXTURE_COMPANY).exists():
            raise CommandError('The fixture already exists. Run with --delete first.')
        # accessible_jobs() is created_by/submitted_for only -- TASK-184 removed the staff exemption --
        # so a job with no created_by is invisible on the board and the fixture would render nothing.
        owner = _owner_user()
        if owner is None:
            raise CommandError('No owner account found (CODEX_CV_OWNER_EMAIL matches no user), so the fixture would be invisible on the board.')
        today = timezone.localdate()
        job = JobLead.objects.create(
            created_by=owner,
            company=FIXTURE_COMPANY,
            title='Delete me after the TASK-175 check',
            url='https://example.invalid/task-175-fixture',
            status='applied',
            status_date=today,
            feedback_due_date=None if due_in_days is None else today + timedelta(days=due_in_days),
        )
        run = MailboxRun.objects.create()
        message = MailboxMessage.objects.create(
            run=run, uid=FIXTURE_UID, sender='hr@example.invalid',
            subject='Ihre Bewerbung - wir melden uns in einigen Wochen',
            body_text='Vielen Dank fuer Ihre Bewerbung. Wir melden uns in einigen Wochen bei Ihnen zurueck.',
            classification='rejection', matched_job=job, received_at=timezone.now(),
        )
        suggestion = MailboxSuggestion.objects.create(
            message=message, job=job, suggestion_type='status_change', payload={'status': 'rejected'},
        )
        self.stdout.write('Created job #%d for %s (status %s, feedback_due_date %s), message uid %d, pending suggestion #%d.' % (
            job.id, owner.username, job.status, job.feedback_due_date, message.uid, suggestion.id))
        self.stdout.write('Delete it again with: manage.py postpone_browser_fixture --delete')
