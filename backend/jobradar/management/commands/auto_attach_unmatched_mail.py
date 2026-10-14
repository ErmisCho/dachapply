from django.core.management.base import BaseCommand

from jobradar.management.commands.rematch_sender_domain_messages import _console_safe
from jobradar.services.mailbox import auto_attach_unmatched_messages


class Command(BaseCommand):
    help = (
        'TASK-291 AC3: one-off back-catalogue pass -- every stored unmatched, undismissed, inbound '
        "message is attached to its Gmail thread's job, or to a confident single suggestion "
        '(services.mailbox.auto_attach_job, the same rule the live mailbox check uses). Attaches '
        'exactly like the panel\'s Attach button: pending suggestions only, no drafts, no status '
        'change. Safe to re-run: a message the owner detached is never re-attached. '
        'Dry run by default; --yes actually attaches.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--yes', action='store_true', help='Actually attach. Without it the command only reports what it would do.')

    def handle(self, *args, **opts):
        results = auto_attach_unmatched_messages(dry_run=not opts['yes'])
        if not results:
            self.stdout.write('No unmatched message follows a matched thread or has a confident suggestion. Nothing to do.')
            return
        total = sum(row['message_count'] for row in results)
        for row in results:
            job = row['job']
            self.stdout.write(_console_safe(f"  job {job.id} ({job.company} -- {job.title}): {row['message_count']} message(s)"))
            for message in row['messages']:
                self.stdout.write(_console_safe(f"    - message {message.pk}: {message.sender} -- {message.subject}"))
        if opts['yes']:
            self.stdout.write(self.style.SUCCESS(f'Attached {total} message(s) across {len(results)} job(s).'))
        else:
            self.stdout.write(self.style.WARNING(f'Dry run: {total} message(s) across {len(results)} job(s) would be attached. Re-run with --yes to act.'))
