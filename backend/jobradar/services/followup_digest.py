"""Daily actionable reminder digest for due follow-ups and overdue feedback."""
import logging
from html import escape

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db import DatabaseError, IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from jobradar.models import ApplicationNote, FollowUp, JobLead, MailboxDraft, MailboxMessage, ScheduledTaskRun

logger = logging.getLogger(__name__)

TASK_NAME = 'followup_digest_daily'
CLOSED_STATUSES = ['rejected', 'withdrawn', 'skipped', 'archived']


def owned_jobs(user):
    """Jobs this user is personally responsible for, never every row visible to staff."""
    return JobLead.objects.filter(Q(created_by=user) | Q(submitted_for=user))


def digest_items(user, today):
    """(due follow-ups, jobs whose expected feedback date has passed) for one user."""
    jobs = owned_jobs(user)
    followups = list(FollowUp.objects.filter(job__in=jobs, completed=False, follow_up_date__lte=today).select_related('job').order_by('follow_up_date'))
    overdue_feedback = list(jobs.filter(feedback_due_date__lte=today).exclude(status__in=CLOSED_STATUSES).order_by('feedback_due_date'))
    return followups, overdue_feedback


def _latest_drafts(job_ids):
    drafts = {}
    for draft in MailboxDraft.objects.filter(job_id__in=job_ids, sent_at__isnull=True).order_by('job_id', '-created_at'):
        if draft.job_id not in drafts or (drafts[draft.job_id].status != 'written' and draft.status == 'written'):
            drafts[draft.job_id] = draft
    return drafts


def _digest_rows(user, followups, overdue_feedback):
    from jobradar.services.mailbox import _reply_from_address, gmail_conversation_url

    items = [('followup', item.job, item.follow_up_date, item.reason) for item in followups]
    items += [('feedback', job, job.feedback_due_date, f'status: {job.get_status_display()}') for job in overdue_feedback]
    drafts = _latest_drafts({job.id for _, job, _, _ in items})
    frontend = (settings.FRONTEND_URL or '').rstrip('/')
    authuser = _reply_from_address() or user.email
    rows = []
    for kind, job, due, detail in items:
        draft = drafts.get(job.id)
        gmail_url = ''
        if draft and draft.status == 'written' and draft.gmail_message_id:
            gmail_url = gmail_conversation_url(draft.gmail_message_id, authuser=authuser, draft=True)
        if draft is None:
            draft_note = 'No reply draft was generated for this item.'
        elif draft.status == 'blocked':
            draft_note = f'Reply not drafted: {draft.block_reason}'
        elif not draft.gmail_message_id:
            draft_note = 'Reply draft is ready in Gmail, but this older row has no direct link.'
        else:
            draft_note = 'Reply draft ready in Gmail.'
        rows.append({
            'kind': kind,
            'job': job,
            'due': due,
            'detail': detail,
            'draft': draft,
            'draft_note': draft_note,
            'gmail_url': gmail_url,
            'job_url': f'{frontend}/jobs/{job.id}#follow-up-action' if frontend else '',
        })
    return rows


def digest_body(followups, overdue_feedback, user=None):
    user = user or (followups[0].job.created_by if followups else overdue_feedback[0].created_by)
    rows = _digest_rows(user, followups, overdue_feedback)
    lines = ['Hello,', '']
    for kind, heading in [('followup', 'Follow-ups due'), ('feedback', 'Feedback overdue')]:
        section = [row for row in rows if row['kind'] == kind]
        if not section:
            continue
        lines.append(f'{heading} ({len(section)}):')
        for row in section:
            job = row['job']
            label = 'due' if kind == 'followup' else 'expected by'
            lines.append(f'- {job.company} - {job.title} - {label} {row["due"]}' + (f' - {row["detail"]}' if row['detail'] else ''))
            lines.append(f'  {row["draft_note"]}')
            if row['gmail_url']:
                lines.append(f'  Open exact Gmail draft: {row["gmail_url"]}')
            if row['job_url']:
                lines.append(f'  Review job and confirm sent: {row["job_url"]}')
        lines.append('')
    lines.append('You can turn these reminders off in your DACHApply profile settings.')
    return '\n'.join(lines)


def digest_html(followups, overdue_feedback, user):
    rows = _digest_rows(user, followups, overdue_feedback)
    sections = []
    button = 'display:inline-block;padding:10px 14px;margin:8px 8px 0 0;border-radius:8px;background:#1d4ed8;color:#fff;text-decoration:none;font-weight:600'
    for kind, heading in [('followup', 'Follow-ups due'), ('feedback', 'Feedback overdue')]:
        section = [row for row in rows if row['kind'] == kind]
        if not section:
            continue
        cards = []
        for row in section:
            job = row['job']
            links = ''
            if row['gmail_url']:
                links += f'<a style="{button}" href="{escape(row["gmail_url"], quote=True)}">Open Gmail draft</a>'
            if row['job_url']:
                links += f'<a style="{button};background:#475569" href="{escape(row["job_url"], quote=True)}">Review in DACHApply</a>'
            cards.append(
                '<li style="margin:0 0 14px;padding:14px;border:1px solid #e2e8f0;border-radius:10px">'
                f'<strong>{escape(job.company)} — {escape(job.title)}</strong><br>'
                f'<span>{escape(str(row["due"]))} · {escape(row["detail"])}</span><br>'
                f'<span>{escape(row["draft_note"])}</span><br>{links}</li>'
            )
        sections.append(f'<h2>{heading} ({len(section)})</h2><ul style="list-style:none;padding:0">{"".join(cards)}</ul>')
    return (
        '<html><body style="font-family:Arial,sans-serif;color:#0f172a">'
        '<p>Hello,</p>' + ''.join(sections) +
        '<p style="color:#64748b">You can turn these reminders off in your DACHApply profile settings.</p>'
        '</body></html>'
    )


@transaction.atomic
def record_followup_sent(followup, draft, user, next_date=None, sent_at=None):
    """Record one exact draft as sent and silence both reminder clocks atomically."""
    followup = FollowUp.objects.select_for_update().select_related('job').get(pk=followup.pk)
    draft = MailboxDraft.objects.select_for_update().get(pk=draft.pk)
    if draft.job_id != followup.job_id or draft.status != 'written':
        raise ValueError('The selected written draft does not belong to this follow-up.')
    if followup.sent_at:
        return followup, None, False
    if draft.sent_at:
        raise ValueError('This Gmail draft was already recorded as sent.')

    sent_at = sent_at or timezone.now()
    if next_date and next_date <= timezone.localdate(sent_at):
        raise ValueError('next_follow_up_date must be after the sent date.')

    followup.completed = True
    followup.sent_at = sent_at
    followup.save(update_fields=['completed', 'sent_at', 'updated_at'])
    draft.sent_at = sent_at
    draft.save(update_fields=['sent_at'])
    JobLead.objects.filter(pk=followup.job_id).update(feedback_due_date=None)

    draft_name = f'Gmail draft {draft.gmail_draft_id}' if draft.gmail_draft_id else f'DACHApply draft #{draft.pk}'
    note = f'Follow-up sent on {timezone.localdate(sent_at).isoformat()} using {draft_name}: {draft.subject or "(no subject)"}.'
    next_followup = None
    if next_date:
        next_followup = FollowUp.objects.filter(job_id=followup.job_id, completed=False, follow_up_date=next_date).first()
        if next_followup is None:
            next_followup = FollowUp.objects.create(
                job_id=followup.job_id,
                follow_up_date=next_date,
                reason=f'Follow up again after {draft.subject or draft_name}'[:250],
            )
        note += f' Next follow-up scheduled for {next_date.isoformat()}.'
    ApplicationNote.objects.create(job_id=followup.job_id, note_type='follow_up', note=note, created_by=user)
    return followup, next_followup, True


@transaction.atomic
def record_job_followup_sent(job, draft, user, next_date=None, sent_at=None, followup_id=None):
    """Record a due FollowUp, or the job's overdue feedback reminder when no FollowUp exists."""
    job = JobLead.objects.select_for_update().get(pk=job.pk)
    today = timezone.localdate(sent_at) if sent_at else timezone.localdate()
    due_followups = FollowUp.objects.select_for_update().filter(
        job=job, completed=False, follow_up_date__lte=today,
    )
    followup = due_followups.filter(pk=followup_id).first() if followup_id else due_followups.order_by('follow_up_date', 'id').first()
    if followup_id and followup is None:
        raise ValueError('The selected follow-up is not due for this job.')
    if followup is None:
        if not job.feedback_due_date or job.feedback_due_date > today:
            raise ValueError('This job has no due follow-up reminder.')
        followup = FollowUp.objects.create(
            job=job, follow_up_date=today, reason='Follow-up sent after expected feedback',
        )
    return record_followup_sent(followup, draft, user, next_date=next_date, sent_at=sent_at)


def reconcile_sent_followups(transport, user):
    """Auto-confirm only when the draft vanished AND a newer owner message proves it was sent."""
    if not hasattr(transport, 'list_draft_ids'):
        return 0
    today = timezone.localdate()
    candidates = list(
        MailboxDraft.objects.filter(
            Q(job__followups__completed=False, job__followups__follow_up_date__lte=today) |
            Q(job__feedback_due_date__lte=today),
            job__in=owned_jobs(user), status='written', sent_at__isnull=True,
        ).exclude(gmail_draft_id='').select_related('job', 'message').distinct()
    )
    if not candidates:
        return 0
    try:
        active_ids = set(transport.list_draft_ids())
    except (RuntimeError, OSError) as exc:
        logger.warning('Could not check Gmail draft ids for sent follow-ups: %s', exc)
        return 0

    recorded = 0
    for draft in candidates:
        if draft.gmail_draft_id in active_ids:
            continue
        thread_id = draft.gmail_thread_id or draft.message.thread_id
        if not thread_id or not MailboxMessage.objects.filter(
            matched_job_id=draft.job_id,
            thread_id=thread_id,
            sent_by_owner=True,
            received_at__gt=draft.created_at,
        ).exists():
            continue
        try:
            _, _, changed = record_job_followup_sent(draft.job, draft, user)
            recorded += int(changed)
        except ValueError:
            continue
    return recorded


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
    send_mail(
        subject,
        digest_body(followups, overdue_feedback, user),
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
        html_message=digest_html(followups, overdue_feedback, user),
    )
    return True


def _claim_today(now):
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
    """Send today's digests once; one user's failure never stops the rest."""
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
