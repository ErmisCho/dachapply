"""Daily plain-text reminder digest for due follow-ups and overdue feedback.

Rides the existing demo-seed daily tick (services/demo_scheduler._scheduler_loop) rather than
adding celery or cron: one more task type, its own ScheduledTaskRun row, its own day guard.
"""
import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db import DatabaseError, IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from jobradar.models import FollowUp, JobLead, ScheduledTaskRun

logger = logging.getLogger(__name__)

TASK_NAME = 'followup_digest_daily'
CLOSED_STATUSES = ['rejected', 'withdrawn', 'skipped', 'archived']


def owned_jobs(user):
    """Jobs this user is personally responsible for.

    Deliberately not services.access.accessible_jobs: that grants staff every row in the
    table, which is right for the admin API and very wrong for a personal reminder email.
    """
    return JobLead.objects.filter(Q(created_by=user) | Q(submitted_for=user))


def digest_items(user, today):
    """(due follow-ups, jobs whose expected feedback date has passed) for one user."""
    jobs = owned_jobs(user)
    followups = list(FollowUp.objects.filter(job__in=jobs, completed=False, follow_up_date__lte=today).select_related('job').order_by('follow_up_date'))
    overdue_feedback = list(jobs.filter(feedback_due_date__lte=today).exclude(status__in=CLOSED_STATUSES).order_by('feedback_due_date'))
    return followups, overdue_feedback


def digest_body(followups, overdue_feedback):
    lines = ['Hello,', '']
    if followups:
        lines.append(f'Follow-ups due ({len(followups)}):')
        lines += [f'- {f.job.company} - {f.job.title} - due {f.follow_up_date}' + (f' - {f.reason}' if f.reason else '') for f in followups]
        lines.append('')
    if overdue_feedback:
        lines.append(f'Feedback overdue ({len(overdue_feedback)}):')
        lines += [f'- {j.company} - {j.title} - expected by {j.feedback_due_date} (status: {j.get_status_display()})' for j in overdue_feedback]
        lines.append('')
    if settings.FRONTEND_URL:
        lines += [f'Open your board: {settings.FRONTEND_URL}', '']
    lines.append('You can turn these reminders off in your DACHApply profile settings.')
    return '\n'.join(lines)


def send_digest(user, today):
    """Mail one user their digest. Returns True only when an email was actually sent."""
    if not user.email:
        return False
    profile = getattr(user, 'jobradar_profile', None)
    if profile is not None and not profile.follow_up_digest_enabled:
        return False
    followups, overdue_feedback = digest_items(user, today)
    if not followups and not overdue_feedback:
        return False
    count = len(followups) + len(overdue_feedback)
    subject = f'DACHApply reminders: {count} item{"s" if count != 1 else ""} need attention'
    send_mail(subject, digest_body(followups, overdue_feedback), settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False)
    return True


def _claim_today(now):
    """Claim today's digest run, or return False if it already ran today.

    Same select_for_update day guard as demo_scheduler.seed_demo_if_due; kept local rather
    than shared because that function's failure handling is pinned by its own regression test.
    """
    try:
        with transaction.atomic():
            try:
                task, _ = ScheduledTaskRun.objects.select_for_update().get_or_create(name=TASK_NAME)
            except IntegrityError:
                task = ScheduledTaskRun.objects.select_for_update().get(name=TASK_NAME)
            last = timezone.localtime(task.last_run_at) if task.last_run_at else None
            if last and last.date() == now.date():
                return False
            task.last_run_at = timezone.now()
            task.save(update_fields=['last_run_at', 'updated_at'])
            return True
    except DatabaseError as exc:
        logger.warning('Could not claim follow-up digest task: %s', exc)
        return False


def send_due_digests():
    """Send today's digests once. Returns the number of emails sent.

    Idempotent per local day: a scheduler retry finds the run already claimed and sends
    nothing. One user's failure (no mailbox, SMTP refusal) is logged and skipped so the
    rest of the batch still goes out.
    """
    now = timezone.localtime(timezone.now())
    if not _claim_today(now):
        return 0
    today = now.date()
    sent = 0
    for user in get_user_model().objects.filter(is_active=True).select_related('jobradar_profile'):
        try:
            if send_digest(user, today):
                sent += 1
        except Exception:
            logger.exception('Follow-up digest failed for user_id=%s', user.pk)
    return sent
