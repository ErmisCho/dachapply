import logging
from html import escape

from django.contrib.auth import authenticate, login, logout, get_user_model
from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.cache import cache
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import send_mail
from django.db import connection, transaction
from django.db.models import Avg, Case, Count, Exists, F, IntegerField, Min, OuterRef, Q, Value, When
from django.db.models.functions import Substr
from django.http import HttpResponse
from django.utils import timezone
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import viewsets, status
from rest_framework.decorators import api_view, permission_classes, action, throttle_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from .models import JobLead, JobEvaluation, ApplicationNote, FollowUp, MailboxDraft, MailboxMessage, MailboxRun, MailboxSuggestion, PracticeSession, UserProfile, InviteCode
from .serializers import CandidateProfileSerializer, JobLeadSerializer, JobLeadListSerializer, JobEvaluationSerializer, ApplicationNoteSerializer, FollowUpSerializer, MailboxDraftSerializer, MailboxMessageListSerializer, MailboxMessageSerializer, MailboxMessageWithSuggestionsSerializer, MailboxRunSerializer, MailboxSuggestionSerializer, PracticeEvaluateSerializer, PracticeSessionSerializer, PublicSubmissionSerializer, invalid_email_addresses, normalize_job_url
from .services.prompt_builder import build_prompt, build_enrichment_prompt, build_bulk_links_prompt, build_combined_prompt, build_candidate_profile_text, has_candidate_profile, user_profile_settings
from .services.json_importer import import_any_json, duplicate_title
from .services.exporters import jobs_json, jobs_csv, chatgpt_brief
from .services.user_data_portability import APP_NAME, SCHEMA_VERSION, build_user_export, export_user_data_csv, export_user_data_xlsx, import_user_export, parse_import_payload
from .services.access import accessible_jobs, job_create_defaults, owned_by, submitted_away_jobs
from .services.cleaning import clean_job_location
from .services.job_replace import replace_job_with_supplied_data
from .services.demo_data import DEMO_PASSWORD, DEMO_USERNAME, ensure_demo_user
from .services.interview_coach import analyze_answer, suggest_questions
from .services import mailbox, mailbox_tasks
from .services.mailbox import apply_suggestion, attach_message_to_job, dismiss_suggestion, suggest_job_for_message
from .services.followup_digest import owned_jobs
from .services.draft_chat import ChatTurn, run_chat_turn
from .services.analytics import record_demo_click
from .services.cv_generator import ARTIFACT_KEYS, available_model_options, decode_correction_image, generation_preview, is_cv_owner, latest_generated_sources, load_candidate_evidence, reveal_artifact_folder, validate_model_capability
from .services.cv_tasks import cancel_cv_task, get_cv_task, get_cv_task_download, start_cv_compile_task, start_cv_revision, start_cv_task
from .services.email_verification import email_verification_token, is_email_verified, mark_verified, send_verification_email, unverified_email_response
from .throttles import CVGenerationUserThrottle, EmailVerificationIPThrottle, ImportUserThrottle, LoginAccountThrottle, LoginIPThrottle, PasswordResetConfirmIPThrottle, PasswordResetEmailThrottle, PasswordResetIPThrottle, PublicSubmitIPThrottle, RegisterIPThrottle


logger = logging.getLogger(__name__)

# Shipped in /api/auth/me/ so the board badges read the same numbers stale_rank orders by,
# instead of the frontend keeping its own copy of them.
BOARD_THRESHOLDS = {
    'stale_applied_days': JobLead.STALE_APPLIED_DAYS,
    'stale_unapplied_days': JobLead.STALE_UNAPPLIED_DAYS,
    'deadline_soon_days': JobLead.DEADLINE_SOON_DAYS,
    'unapplied_statuses': JobLead.UNAPPLIED_STATUSES,
    'dated_statuses': JobLead.DATED_STATUSES,
    # TASK-143 AC1: published for the same reason as the two lists above -- the frontend needs to
    # know which statuses are still worth acting on (it hides mailbox conversations for the rest),
    # and a second copy of the list in App.tsx is the bug TASK-96 exists to delete. The client keeps
    # a fallback for a pre-auth render, exactly as it already does for unapplied_statuses.
    'actionable_statuses': JobLead.ACTIONABLE_STATUSES,
}


# TASK-145 AC1/AC3: the board's default ordering -- attention order first (new, then interview,
# then everything else in pipeline order, closed statuses last -- see _attention_rank below),
# then the age/urgency formula as tiebreakers within a group. Sorting is an opt-in override of
# this, never a replacement -- ?ordering= absent, empty or unrecognised lands here.
# stale_rank is demoted, not deleted (AC3): it no longer leads (the owner declined that variant),
# but it is still the second key, so two jobs in the same attention group still surface an
# imminent deadline or a stale one before the rest -- ordering *within* a group is unchanged from
# before this task.
DEFAULT_BOARD_ORDERING = ('attention_rank', 'stale_rank', 'priority_rank', '-evaluations__fit_score', '-created_at')

# TASK-97/TASK-108's sort control. The query parameter is a lookup *key*, never an argument to
# order_by(): passing it through would let a client order by any related column
# (?ordering=-created_by__password) and read values off the resulting row order, which is
# information disclosure, not just untidy. An unknown key simply misses the dict.
# 'status' points at status_pipeline_rank (built below from JobLead.STATUSES), not attention_rank
# -- attention_rank is the grouped order DEFAULT_BOARD_ORDERING depends on (new, then interview,
# then pipeline order for the rest), which is wrong for a user explicitly sorting by pipeline stage.
BOARD_ORDERINGS = {
    'status': 'status_pipeline_rank',
    'fit_score': 'evaluations__fit_score',
    'priority': 'priority_rank',
    'created_at': 'created_at',
    'applied_at': 'applied_at',
    'updated_at': 'updated_at',
    'feedback_due_date': 'feedback_due_date',
}


def _status_pipeline_rank():
    """Case/When generated from JobLead.STATUSES so a status added to the model can't
    silently fail to sort -- the pipeline order is never restated as a second literal list."""
    whens = [When(status=s, then=Value(i)) for i, (s, _label) in enumerate(JobLead.STATUSES)]
    return Case(*whens, default=Value(len(JobLead.STATUSES)), output_field=IntegerField())


def _attention_rank():
    """TASK-145 AC1/AC2: the board's default GROUP order -- new first, interview second, then
    every other status in the model's own pipeline order, closed statuses last -- built from
    JobLead.STATUSES the same way _status_pipeline_rank() is above, so a status added to the
    model can't silently sort into an arbitrary position. 'new' and 'interview' are pulled out to
    ranks 0 and 1; everything else keeps its pipeline index offset by 2, which preserves their
    relative (pipeline) order without restating it as a second list -- STATUSES already lists
    reviewed/to_apply/applied/offer/accepted before the closed statuses, so offsetting by 2 keeps
    them in that same order after 'new' and 'interview' are pulled to the front.
    """
    whens = [
        When(status=s, then=Value(0 if s == 'new' else 1 if s == 'interview' else 2 + i))
        for i, (s, _label) in enumerate(JobLead.STATUSES)
    ]
    return Case(*whens, default=Value(2 + len(JobLead.STATUSES)), output_field=IntegerField())


def _ordering_expr(key, descending):
    field = BOARD_ORDERINGS[key]
    if key == 'feedback_due_date':
        # nulls_last both directions: most rows have no feedback date, and the point of this
        # sort is to surface the ones that do rather than let nulls float to the top on desc.
        return F(field).desc(nulls_last=True) if descending else F(field).asc(nulls_last=True)
    return f'-{field}' if descending else field


def parse_board_ordering(raw):
    """TASK-108 wire contract: '?ordering=status,-fit_score' -- comma-separated keys, each an
    optional leading '-' for descending. Unknown or duplicate keys are dropped rather than
    erroring, so a stale bookmark degrades instead of breaking; at most 3 keys are honoured;
    '-created_at' then 'id' are always appended as final tiebreakers so pagination can't
    interleave. Falls back to DEFAULT_BOARD_ORDERING when nothing valid remains. Only
    BOARD_ORDERINGS' values ever reach order_by() -- a raw query token that isn't one of its
    keys never does.
    """
    seen = set()
    exprs = []
    for token in (raw or '').split(','):
        token = token.strip()
        if not token:
            continue
        descending = token.startswith('-')
        key = token[1:] if descending else token
        if key not in BOARD_ORDERINGS or key in seen:
            continue
        seen.add(key)
        exprs.append(_ordering_expr(key, descending))
        if len(exprs) == 3:
            break
    return (*exprs, '-created_at', 'id') if exprs else DEFAULT_BOARD_ORDERING


# "Reached interview" is about the journey, not the current column. A job now in `offer`,
# `accepted`, or `rejected` obviously interviewed; counting only status='interview' would
# undercount exactly the jobs that converted best. There is no status history, so past
# interviews of a job that has since moved to a closed status are recovered from the
# interview fields the board already records.
# Known gap: a job rejected *after* an offer leaves no offer trace, so REACHED_OFFER
# undercounts those. Recording an offer date would be the fix, and needs its own task.
REACHED_INTERVIEW = Q(status__in=['interview', 'offer', 'accepted']) | Q(interview_stage__isnull=False) | Q(interview_at__isnull=False)
REACHED_OFFER = Q(status__in=['offer', 'accepted'])


def conversion_rate(numerator, denominator):
    """Percentage to one decimal, or None when the denominator is empty.

    None, not 0: with no applications the rate is undefined, and a rendered 0% would read
    as "you convert nothing" rather than "there is nothing to measure yet".
    """
    return round(100 * numerator / denominator, 1) if denominator else None


def funnel_counts(applied_jobs):
    """applied -> interview -> offer over one cohort of applications.

    The cohort is always jobs with an `applied_at` (TASK-76's write-once stamp), never jobs
    in the current `applied` status, so a job walked on to `rejected` still counts as an
    application. Numerators are intersected with the same cohort, so a job that reached
    interview without ever being marked applied cannot push a rate above 100% -- it is
    reported separately as `interviews_without_application` instead of being hidden.
    """
    applications = applied_jobs.count()
    interviews = applied_jobs.filter(REACHED_INTERVIEW).count()
    offers = applied_jobs.filter(REACHED_OFFER).count()
    return {
        'applications': applications,
        'interviews': interviews,
        'offers': offers,
        'applied_to_interview_rate': conversion_rate(interviews, applications),
        'interview_to_offer_rate': conversion_rate(offers, interviews),
    }


def source_effectiveness(applied_jobs):
    """Applications and interview rate per `source`, busiest source first.

    Grouped over the application cohort, so a source that has never produced an application
    does not dilute the table. `source` is emitted raw; '' is a real bucket (jobs added
    without a source) and the frontend labels it.
    """
    rows = applied_jobs.values('source').annotate(applications=Count('id'), interviews=Count('id', filter=REACHED_INTERVIEW)).order_by('-applications', 'source')
    return [{'source': row['source'], 'applications': row['applications'], 'interviews': row['interviews'],
             'interview_rate': conversion_rate(row['interviews'], row['applications'])} for row in rows]


def password_rejection(password, user=None):
    """Run AUTH_PASSWORD_VALIDATORS; return a 400 Response, or None when the password is fine.

    Every password-setting endpoint routes through here so the validators cannot be enforced on
    one path and forgotten on another. `user` enables UserAttributeSimilarityValidator and may be
    an unsaved instance. The {'detail': str} shape is what the frontend already renders.
    """
    try:
        validate_password(password, user)
    except DjangoValidationError as exc:
        return Response({'detail': ' '.join(exc.messages)}, status=400)
    return None


# TASK-84: what the submitter of a handed-off job may see of it. Everything the recipient writes
# afterwards -- evaluations, interview fields, dates, the workflow status itself -- is the
# recipient's, so the projection is default-deny: every serialized field is emptied unless it is
# part of the submission the submitter made. A field added to JobLead later therefore cannot leak
# by being forgotten here, which a blacklist would have allowed.
SUBMISSION_VISIBLE_FIELDS = ('id','company','title','url','location','source','submitted_by','submitter_reason','salary_info','language_requirements','work_mode','created_at','created_by_username','created_by_email','submitted_for_username','submitted_for_email')
# The coarse status the submitter gets instead of the real one, expressed in the board's own
# vocabulary so no client needs to learn a new value: still live, or done with.
CLOSED_STATUSES = ('rejected','withdrawn','skipped','archived')


def submission_row(row):
    limited={key: ('' if isinstance(value, str) else None) for key, value in row.items()}
    limited.update({key: row[key] for key in SUBMISSION_VISIBLE_FIELDS if key in row})
    limited['status']='archived' if row.get('status') in CLOSED_STATUSES else 'new'
    # Marks the row as a submission receipt rather than a job the caller owns, so a client can tell
    # the two apart without inferring it from blank fields.
    limited['submission_only']=True
    return limited


def find_existing_by_url(url, owner=None, queryset=None):
    if not url: return None
    url=normalize_job_url(url)
    variants={url, url.rstrip('/')}
    if not url.endswith('/'): variants.add(url + '/')
    qs=(queryset if queryset is not None else JobLead.objects.all()).filter(url__in=variants)
    if owner:
        qs=qs.filter(Q(created_by=owner)|Q(submitted_for=owner))
    return qs.first()


def extract_links(text):
    import re
    text=text or ''
    found=re.findall(r'https?://[^\s,;]+|https-[^\s,;]+|http-[^\s,;]+|(?:www\.)?[-\w]+\.[a-zA-Z]{2,}[^\s,;]*', text)
    links=[]
    for f in found:
        if '@' in f: continue
        link=normalize_job_url(f.strip('()[]<>"\''))
        if link and link not in links: links.append(link)
    return links

@api_view(['GET'])
@permission_classes([AllowAny])
def health(request):
    database = 'ok'
    status_code = 200
    try:
        connection.ensure_connection()
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
    except Exception:
        logger.exception('Health check database probe failed')
        database = 'unavailable'
        status_code = 503
    return Response({'status': 'ok' if status_code == 200 else 'degraded', 'database': database}, status=status_code)


# TASK-160: cache key the mailbox watchdog alert's cooldown lives under. A plain module constant,
# not per-failure like _alert_key() in config/settings.py -- there is only one kind of alert here
# (the mailbox check is broken), so there is nothing to key by.
MAILBOX_HEALTH_ALERT_CACHE_KEY = 'mailbox_health_watchdog_alert_sent'

# TASK-161 AC5 (TASK-169: superseded as the ACTIVE window -- kept only as the default's source of
# truth, see _identify_window() below): the `unmatched` action's recency window for its two
# low-consequence classes (application_confirmed, recruiter_reply -- see
# UNMATCHED_LOW_CONSEQUENCE_CLASSIFICATIONS below). 90 days, not a rounder number, because it is
# where the measured age distribution actually breaks: 68 of the panel's 321 rows fall inside 90 days
# and 253 outside it, and that boundary is where live mail flow ends and the
# backfill_historical_mail/ingest_threads bulk import begins (see task-161's Implementation Notes for
# the full cumulative distribution). It also happens to equal the 3 months TASK-169 asked for as the
# per-account DEFAULT -- coincidence, not a rename: UserProfile.mailbox_identify_window_months is a
# real per-account setting an owner can change, this constant is not.
UNMATCHED_RECENCY_WINDOW_DAYS = 90
# rank 0 (never age-filtered UNDER THE DEFAULT window -- TASK-169 AC7 changes this once the owner sets
# an EXPLICIT window, see _identify_window()): the two classes attaching can act on regardless of the
# target job's state -- set to rejected/interview. rank 1 (age-filtered): only useful for a subset of
# jobs (application_confirmed backdates an unapplied job; recruiter_reply clears a feedback clock a job
# may not have) and is a data-repair chore rather than a decision once it is this old. rank 2
# (age-filtered): uncertain and anything else not in the two lists above.
UNMATCHED_HIGH_CONSEQUENCE_CLASSIFICATIONS = ('rejection', 'interview_invitation')
UNMATCHED_LOW_CONSEQUENCE_CLASSIFICATIONS = ('application_confirmed', 'recruiter_reply')


def _identify_window(profile):
    """TASK-169: the identification window's effective length in days, and whether the OWNER
    explicitly chose it -- (days, explicit). `profile.mailbox_identify_window_months` is None until
    the owner sets it (the model field's own comment explains why null, not 0, means "unset"); this
    is where that null gets read as the 3-month default (UNMATCHED_RECENCY_WINDOW_DAYS, this
    module's own source of truth for that default -- see its comment above). 30 days/month, the same
    convention services.mailbox._lookback_days already uses for mailbox_lookback_months, so the two
    settings stay comparable at a glance.

    AC7: `explicit` is what `unmatched` below uses to decide whether rank 0 (rejection/
    interview_invitation) is bound by this window too -- a DEFAULT the owner never touched must never
    bury them (TASK-161 measured 15 of 41 currently-unattached ones are over a year old), but a window
    the owner DID set is honoured even there, visibly and reversibly (its own separately-reported,
    revealable count).
    """
    months = profile.mailbox_identify_window_months if profile else None
    if months is None:
        return UNMATCHED_RECENCY_WINDOW_DAYS, False
    return months * 30, True
# TASK-163 fix 1 (coordinator re-measurement, 2026-08-21): a tracked company's name routinely sits
# past BODY_PREVIEW_CHARS (300) -- matching against that preview alone found only 8 of 321 rows a
# suggestion, because the name simply is not in the first 300 characters. A SECOND, separately bounded
# Substr(...) annotation (match_text, below) gives suggest_job_for_message more text to search without
# undoing the point of body_preview: still ONE query, still never touches the deferred body_text
# column, and match_text is not added to MailboxMessageListSerializer.Meta.fields, so it never reaches
# the client -- the response payload is unchanged.
UNMATCHED_MATCH_TEXT_CHARS = 2000


def _mailbox_health():
    """TASK-160 AC1: health computed from MailboxRun rows alone -- no call to Gmail or to the
    owner's machine, which is the entire point (the deployed site reads the same database the
    local check writes to, but can reach neither Gmail nor the laptop itself).

    Returns (status, detail): `status` is the coarse value AC6 allows the endpoint to expose
    ('ok' | 'failing' | 'stale'); `detail` is for the alert email only, never for the response body.

    A failing latest run always wins over staleness: whatever the last successful run looked like,
    a fresh error is the more specific, more actionable thing to report. 'successful' matches the
    existing idiom in services.mailbox.mailbox_check_estimate -- finished_at set and error blank --
    so a legitimate skip (quiet hours, disabled, outside the check window) still counts as evidence
    the checker itself is alive, which is what staleness is actually asking about.
    """
    latest = MailboxRun.objects.order_by('-started_at').first()
    if latest is not None and latest.error:
        return 'failing', latest.error
    last_success = MailboxRun.objects.filter(finished_at__isnull=False, error='').order_by('-finished_at').first()
    cutoff = timezone.now() - timezone.timedelta(hours=settings.MAILBOX_STALE_ALERT_HOURS)
    if last_success is None or last_success.finished_at < cutoff:
        if last_success is None:
            detail = 'No successful run has ever been recorded.'
        else:
            hours_ago = round((timezone.now() - last_success.finished_at).total_seconds() / 3600, 1)
            detail = f'No successful run in over {hours_ago} hours (last one was {hours_ago} hours ago).'
        return 'stale', detail
    return 'ok', ''


def _send_mailbox_health_alert(status_value, detail):
    """TASK-160 AC2/AC3/AC4/AC6: sends through django.core.mail directly, not through the logging
    handler -- mail_admins carries require_debug_false, which would block this locally even if the
    owner's machine had SMTP configured to begin with (it does not). Recipients are whatever the
    deployed site already has configured for TASK-88's alerting (settings.ADMINS, built from
    ERROR_ALERT_EMAILS): no second address to configure, no new shared secret (see the task's
    Implementation Notes).

    AC4: at most one alert per settings.ERROR_ALERT_COOLDOWN_SECONDS -- the same cooldown idea
    config.settings.ErrorAlertCooldown uses, reused via the cache rather than a second mechanism.
    cache.add() is atomic and only succeeds the first time a key is set, which is exactly "have I
    already alerted for this within the window" without a race between concurrent workers; CACHES is
    DatabaseCache (see settings.py), so this is shared across every worker and process, unlike that
    filter's own admittedly per-process dict.

    Never raises: a broken alert email must not break the health probe it rides on.
    """
    recipients = [address for _name, address in settings.ADMINS]
    if not recipients:
        return  # AC6/task notes: nothing configured means nothing to do, never a crash
    # TASK-185: keyed on the STATUS, not just "an alert was sent", so a check that goes from stale to
    # actively failing still says so once instead of being swallowed by the other status's window.
    # And on the mailbox alert's OWN cooldown (a day by default), not TASK-88's 5-minute error floor
    # -- borrowing that sent the owner 83 identical emails over three and a half days, because this
    # condition persists until a human re-runs an interactive OAuth command.
    if not cache.add(f'{MAILBOX_HEALTH_ALERT_CACHE_KEY}:{status_value}', True,
                     timeout=settings.MAILBOX_HEALTH_ALERT_COOLDOWN_SECONDS):
        return  # already alerted for this status inside the current cooldown window
    reason = f'is failing: {detail}' if status_value == 'failing' else detail
    detail_summary = 'failing' if status_value == 'failing' else (detail.split('(')[0].strip().rstrip('.') or 'stale')
    # TASK-185: the hours were the ONLY thing that varied across the 83 emails, and they were buried
    # in the body, so every subject line read identically and the thread collapsed into noise. In the
    # subject, escalation is visible without opening anything.
    subject = f'DACHApply mailbox check needs attention ({detail_summary})' if detail_summary else 'DACHApply mailbox check needs attention'
    body = (
        f'The DACHApply mailbox check {reason}\n\n'
        'What to do:\n\n'
        '1. Re-authorize the Gmail connection on the machine that runs the check:\n\n'
        '   python manage.py gmail_oauth_setup\n\n'
        '2. If this keeps recurring roughly every 7 days, publish the OAuth consent screen '
        '(Google Cloud Console -> APIs & Services -> OAuth consent screen -> Publish App). While '
        'the app stays in "Testing" publishing status, Google expires the refresh token after '
        'about 7 days of use regardless of whether it is actually being used; publishing the '
        'OAuth consent screen removes that 7-day testing-mode refresh-token expiry entirely.\n'
    )
    try:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, recipients, fail_silently=False)
    except Exception:
        logger.exception('Mailbox health alert email failed to send')


@api_view(['GET'])
@permission_classes([AllowAny])
def mailbox_health(request):
    """TASK-160: lets the DEPLOYED site notice when the mailbox check has stopped working, even
    though the deployed site never runs that check itself -- see backlog/tasks/task-160 for why
    TASK-88's alerting cannot cover this (it runs on the owner's own machine, where DEBUG=True
    blocks the mail_admins handler and there is no SMTP configured anyway).

    AC6: always 200 and a coarse status only, unauthenticated -- /api/health/ stays the uptime
    workflow's up/down signal (do not overload it, per the task notes); this is a separate,
    side-effecting probe the workflow calls in addition, and it must never be able to fail that
    workflow on its own. Nothing about mailbox content (subjects, senders, counts) is exposed here;
    that detail goes only into the alert email, which reaches the owner's own configured address.
    """
    status_value, detail = _mailbox_health()
    if status_value == 'ok':
        # AC4: clear any cooldown key left over from a prior failure, so the NEXT failure alerts
        # promptly instead of riding out a cooldown window that started before the recovery.
        # TASK-185: both status keys, since the cooldown is now per-status. Recovery itself stays
        # deliberately silent -- an "it works again" email to an owner who just fixed it by hand adds
        # nothing they do not already know -- but clearing the keys means the NEXT failure alerts
        # promptly rather than riding out a window that started before the recovery.
        cache.delete_many([f'{MAILBOX_HEALTH_ALERT_CACHE_KEY}:failing',
                           f'{MAILBOX_HEALTH_ALERT_CACHE_KEY}:stale'])
    else:
        _send_mailbox_health_alert(status_value, detail)
    return Response({'status': status_value})


@ensure_csrf_cookie
@api_view(['GET'])
@permission_classes([AllowAny])
def csrf(request): return Response({'detail':'ok'})

@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([LoginIPThrottle, LoginAccountThrottle])
def login_view(request):
    username=(request.data.get('username') or '').strip()
    password=request.data.get('password') or ''
    if username.lower()==DEMO_USERNAME and password==DEMO_PASSWORD:
        record_demo_click(request)
        user,_jobs=ensure_demo_user()
    else:
        user=authenticate(request, username=username, password=password)
    if not user: return Response({'detail':'Invalid credentials'}, status=400)
    login(request, user); return Response({'username':user.username, 'can_generate_cv':is_cv_owner(user)})

@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([RegisterIPThrottle])
def register_view(request):
    email=(request.data.get('email') or request.data.get('username') or '').strip().lower()
    username=email
    password=request.data.get('password') or ''
    User=get_user_model()
    rejected=password_rejection(password, User(username=username, email=email))
    if rejected: return rejected
    if not email or '@' not in email: return Response({'detail':'Valid email is required'}, status=400)
    # TASK-93 AC2: the friend is stored exactly as typed and never looked up here. The old code
    # answered 'Friend username or email not found' on a miss and echoed the friend's username back
    # on a hit, so an anonymous caller could ask this endpoint whether any address has an account.
    # Registration now takes the same path, does the same work and returns the same body either way;
    # the name is resolved when the address is verified, or dropped in silence if it never matches.
    submit_for_lookup=(request.data.get('submit_for_username') or request.data.get('submit_for') or '').strip()[:254]
    if User.objects.filter(Q(username__iexact=email)|Q(email__iexact=email)).exists(): return Response({'detail':'Email already exists'}, status=400)
    user=User.objects.create_user(username=username, email=email, password=password)
    UserProfile.objects.create(user=user, email_verified=False, pending_friend_lookup=submit_for_lookup)
    login(request, user)
    # After login(), which rewrites last_login -- and best effort, so a dead mail host costs the new
    # account a resend from Account settings rather than its registration.
    send_verification_email(user)
    return Response({'username':user.username, 'submit_for_username':None, 'requested_submit_for_username':None, 'is_friend_submitter':False, 'email_verified':False}, status=201)

@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([EmailVerificationIPThrottle])
def verify_email(request):
    """Consume the link from the confirmation email. Idempotent: the token stays valid until it
    expires, so a second click (or a mail client prefetching the URL) succeeds instead of scaring
    the user with an error about a link that already worked."""
    try:
        uid=force_str(urlsafe_base64_decode(request.data.get('uid') or ''))
        user=get_user_model().objects.get(pk=uid)
    except Exception:
        return Response({'detail':'Invalid verification link'}, status=400)
    if not email_verification_token.check_token(user, request.data.get('token') or ''):
        return Response({'detail':'Invalid or expired verification link'}, status=400)
    mark_verified(user)
    return Response({'detail':'Email address confirmed.'})

@api_view(['POST'])
@throttle_classes([EmailVerificationIPThrottle])
def resend_verification_email(request):
    """Authenticated, and only ever sends to request.user.email -- there is no address to supply and
    therefore nothing to enumerate or mail-bomb with."""
    if is_email_verified(request.user):
        return Response({'detail':'Your email address is already confirmed.'})
    if not send_verification_email(request.user):
        return Response({'detail':'We could not send the confirmation email just now. Please try again in a few minutes.'}, status=502)
    return Response({'detail':'Confirmation email sent. Check your inbox, and your spam or promotions folder.'})

@api_view(['POST'])
def logout_view(request): logout(request); return Response({'detail':'logged out'})

@api_view(['POST'])
def change_password(request):
    user=request.user
    current=request.data.get('current_password') or ''
    new=request.data.get('new_password') or request.data.get('password') or ''
    if user.has_usable_password() and not user.check_password(current):
        return Response({'detail':'Current password is incorrect.'}, status=400)
    rejected=password_rejection(new, user)
    if rejected: return rejected
    user.set_password(new); user.save(update_fields=['password'])
    login(request, user)
    return Response({'detail':'Password updated.'})

@api_view(['GET','POST'])
def email_diagnostics(request):
    """Staff-only view of the mail configuration, and a self-addressed test send.

    Password reset answers the same generic string whether or not delivery worked, to avoid
    account enumeration. That is right for the public endpoint but leaves the operator unable to
    tell a broken SMTP config from a missing account, and the server logs are only reachable with
    platform access. This reports the configuration without ever returning a secret, and POST
    surfaces the real exception instead of swallowing it.
    """
    if not request.user.is_staff:
        return Response({'detail':'Not found.'}, status=404)
    config={
        'backend':settings.EMAIL_BACKEND,
        'host':settings.EMAIL_HOST,
        'port':settings.EMAIL_PORT,
        'use_tls':settings.EMAIL_USE_TLS,
        'use_ssl':settings.EMAIL_USE_SSL,
        'default_from_email':settings.DEFAULT_FROM_EMAIL,
        'frontend_url':settings.FRONTEND_URL,
        # Booleans only: the presence of credentials is the diagnostic, the values are never sent.
        'host_user_set':bool(settings.EMAIL_HOST_USER),
        'host_password_set':bool(settings.EMAIL_HOST_PASSWORD),
        'console_backend':settings.EMAIL_BACKEND.endswith('console.EmailBackend'),
    }
    if request.method=='GET':
        return Response(config)
    if not request.user.email:
        return Response({'detail':'Your account has no email address to send to.'}, status=400)
    try:
        sent=send_mail('DACHApply email test', 'If you received this, password reset email delivery works.',
                       settings.DEFAULT_FROM_EMAIL, [request.user.email], fail_silently=False)
    except Exception as exc:
        # Safe to surface: this route is staff-only, so there is nothing to enumerate.
        return Response({'ok':False,'error':f'{type(exc).__name__}: {exc}','config':config}, status=502)
    return Response({'ok':bool(sent),'sent_to':request.user.email,'config':config})


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([PasswordResetIPThrottle, PasswordResetEmailThrottle])
def password_reset_request(request):
    email=(request.data.get('email') or '').strip().lower()
    User=get_user_model(); user=User.objects.filter(email__iexact=email).first()
    if user:
        uid=urlsafe_base64_encode(force_bytes(user.pk)); token=default_token_generator.make_token(user)
        link=f"{settings.FRONTEND_URL}/reset-password/{uid}/{token}"
        try:
            subject='DACHApply password reset request'
            message=(
                'Hello,\n\n'
                'We received a request to reset the password for your DACHApply account.\n\n'
                'To choose a new password, open the secure link below:\n\n'
                f'{link}\n\n'
                'If the button or link does not work, copy and paste the URL into your browser.\n\n'
                'If you did not request this change, you can safely ignore this email. '
                'Your password will remain unchanged.\n\n'
                'For your security, this link can only be used once and may expire.\n\n'
                'Regards,\n'
                'The DACHApply Team'
            )
            safe_link=escape(link, quote=True)
            html_message=f'''<!doctype html>
<html>
  <body style="margin:0;background:#f8fafc;padding:24px;font-family:Arial,Helvetica,sans-serif;color:#0f172a;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:600px;margin:0 auto;background:#ffffff;border:1px solid #e2e8f0;border-radius:16px;overflow:hidden;">
      <tr>
        <td style="padding:24px 28px;background:#0f172a;color:#ffffff;">
          <div style="font-size:20px;font-weight:700;letter-spacing:-0.02em;">DACHApply</div>
          <div style="margin-top:4px;font-size:13px;color:#cbd5e1;">Password reset request</div>
        </td>
      </tr>
      <tr>
        <td style="padding:28px;">
          <h1 style="margin:0 0 12px;font-size:24px;line-height:1.25;color:#0f172a;">Reset your password</h1>
          <p style="margin:0 0 16px;font-size:15px;line-height:1.6;color:#334155;">We received a request to reset the password for your DACHApply account.</p>
          <p style="margin:0 0 24px;font-size:15px;line-height:1.6;color:#334155;">Use the button below to choose a new password.</p>
          <p style="margin:0 0 24px;">
            <a href="{safe_link}" style="display:inline-block;border-radius:999px;background:#0f172a;color:#ffffff;text-decoration:none;font-weight:700;font-size:15px;padding:12px 22px;">Reset password</a>
          </p>
          <p style="margin:0 0 10px;font-size:13px;line-height:1.6;color:#64748b;">If the button does not work, copy and paste this link into your browser:</p>
          <p style="margin:0 0 22px;font-size:13px;line-height:1.6;word-break:break-all;"><a href="{safe_link}" style="color:#2563eb;">{safe_link}</a></p>
          <div style="margin:0 0 22px;padding:14px 16px;border-radius:12px;background:#f8fafc;border:1px solid #e2e8f0;color:#475569;font-size:14px;line-height:1.6;">
            If you did not request this change, you can safely ignore this email. Your password will remain unchanged.
          </div>
          <p style="margin:0;font-size:13px;line-height:1.6;color:#64748b;">For your security, this link can only be used once and may expire.</p>
          <p style="margin:24px 0 0;font-size:15px;line-height:1.6;color:#334155;">Regards,<br>The DACHApply Team</p>
        </td>
      </tr>
    </table>
  </body>
</html>'''
            send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False, html_message=html_message)
        except Exception:
            # Keep the public response generic to avoid account enumeration and
            # never log SMTP credentials or reset tokens.
            logger.exception('Password reset email delivery failed for user_id=%s', user.pk)
    return Response({'detail':'If an account exists for this email, a reset link was sent.'})

@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([PasswordResetConfirmIPThrottle])
def password_reset_confirm(request):
    try:
        uid=force_str(urlsafe_base64_decode(request.data.get('uid') or ''))
        user=get_user_model().objects.get(pk=uid)
    except Exception:
        return Response({'detail':'Invalid reset link'}, status=400)
    token=request.data.get('token') or ''; password=request.data.get('password') or ''
    if not default_token_generator.check_token(user, token): return Response({'detail':'Invalid or expired reset link'}, status=400)
    rejected=password_rejection(password, user)
    if rejected: return rejected
    user.set_password(password); user.save(update_fields=['password'])
    return Response({'detail':'Password reset successful'})

@api_view(['DELETE'])
def delete_account(request):
    user=request.user
    password=request.data.get('password') or request.data.get('current_password') or ''
    if user.has_usable_password() and not user.check_password(password):
        return Response({'detail':'Current password is required to delete your account.'}, status=400)
    with transaction.atomic():
        # TASK-103: this used to be Q(created_by=user)|Q(submitted_for=user), the same "created it
        # is owned it" rule TASK-84 removed from access.owned_by -- it let a friend who only
        # submitted a job for someone else delete the recipient's job (and its evaluations/notes/
        # follow-ups via the cascades below) along with their own account. owned_by(user) is the
        # one ownership rule every other consumer already routes through.
        owned_jobs=JobLead.objects.filter(owned_by(user)).distinct()
        profile_count=1 if hasattr(user, 'jobradar_profile') else 0
        # Count what .delete() actually removed, not a queryset snapshot taken before the delete --
        # JobEvaluation/ApplicationNote/FollowUp cascade off JobLead, so the two numbers diverge.
        _, deleted_by_model=owned_jobs.delete()
        counts={
            'jobs': deleted_by_model.get('jobradar.JobLead', 0),
            'evaluations': deleted_by_model.get('jobradar.JobEvaluation', 0),
            'notes': deleted_by_model.get('jobradar.ApplicationNote', 0),
            'followups': deleted_by_model.get('jobradar.FollowUp', 0),
            'profile': profile_count,
        }
        # Notes this user wrote on a job they do not own (e.g. one submitted for someone else)
        # are the recipient's board content, not this account's -- strip the byline, do not delete
        # someone else's note just because this user authored it.
        ApplicationNote.objects.filter(created_by=user).update(created_by=None)
        logout(request)
        user.delete()
    return Response({'detail':'Account deleted.', 'deleted': counts})

@api_view(['GET'])
def me(request):
    profile=getattr(request.user, 'jobradar_profile', None)
    submit_for=profile.submit_for if profile else None
    requested=profile.requested_submit_for if profile else None
    # candidate_profile_missing is the nudge signal: true means every prompt endpoint will refuse
    # with 400 {'code':'candidate_profile_required'} until the user fills in Settings -> profile.
    return Response({'username':request.user.username, 'is_staff':request.user.is_staff, 'submit_for_username':submit_for.username if submit_for else None, 'requested_submit_for_username':requested.username if requested else None, 'is_friend_submitter':bool(submit_for), 'can_generate_cv':is_cv_owner(request.user), 'candidate_profile_missing':not has_candidate_profile(request.user), 'email_verified':is_email_verified(request.user), 'feedback_url':settings.FEEDBACK_URL, 'board_thresholds':BOARD_THRESHOLDS})

@api_view(['GET','POST'])
def friend_requests(request):
    if request.method=='GET':
        profiles=UserProfile.objects.filter(requested_submit_for=request.user, submit_for__isnull=True).select_related('user')
        return Response([{'username':p.user.username} for p in profiles])
    # TASK-93 AC1: approving hands another account write access to this board, so it waits for a
    # confirmed address. Reading the pending list does not -- it shows the caller who asked for
    # them, which reveals nothing about anyone the caller did not already hear from.
    rejected=unverified_email_response(request.user)
    if rejected: return rejected
    username=(request.data.get('username') or '').strip()
    try: profile=UserProfile.objects.select_related('user').get(user__username=username, requested_submit_for=request.user, submit_for__isnull=True)
    except UserProfile.DoesNotExist: return Response({'detail':'Request not found'}, status=404)
    profile.submit_for=request.user; profile.requested_submit_for=None; profile.save(update_fields=['submit_for','requested_submit_for'])
    return Response({'ok':True,'username':username})

@api_view(['GET','PATCH','PUT'])
def profile_settings(request):
    profile=user_profile_settings(request.user)
    if request.method == 'GET':
        return Response(CandidateProfileSerializer(profile).data)
    ser=CandidateProfileSerializer(profile, data=request.data, partial=True)
    ser.is_valid(raise_exception=True); ser.save()
    return Response(ser.data)

class JobLeadViewSet(viewsets.ModelViewSet):
    serializer_class=JobLeadSerializer
    queryset=JobLead.objects.all().prefetch_related('evaluations')
    def get_serializer_class(self):
        # The list is unpaginated, so every extra field is multiplied by lifetime history.
        return JobLeadListSerializer if self.action == 'list' else JobLeadSerializer
    def get_queryset(self):
        qs=accessible_jobs(self.request.user)
        # Only the list adds jobs handed to somebody else, and list() projects those rows down to
        # the submission itself. Every other action -- detail, mutation, nested notes/evaluations/
        # follow-ups -- stays on accessible_jobs and 404s for them.
        if self.action == 'list':
            qs=qs | submitted_away_jobs(self.request.user)
        qs=qs.prefetch_related('evaluations'); p=self.request.query_params
        if p.get('status'):
            statuses=[s for s in p.get('status','').split(',') if s]
            qs=qs.filter(status__in=statuses)
        elif self.action == 'list':
            qs=qs.exclude(status='archived')
        if p.get('work_mode'): qs=qs.filter(work_mode=p['work_mode'])
        if p.get('company'): qs=qs.filter(company__icontains=p['company'])
        if p.get('location'): qs=qs.filter(location__icontains=p['location'])
        if p.get('priority'):
            priorities=[x for x in p.get('priority','').split(',') if x]
            qs=qs.filter(evaluations__priority__in=priorities)
        if p.get('recommendation'):
            recommendations=[x for x in p.get('recommendation','').split(',') if x]
            qs=qs.filter(evaluations__recommendation__in=recommendations)
        if p.get('min_fit_score'): qs=qs.filter(evaluations__fit_score__gte=p['min_fit_score'])
        if p.get('skill'):
            s=p['skill']; qs=qs.filter(Q(evaluations__matched_skills__icontains=s)|Q(evaluations__required_skills__icontains=s)|Q(original_source_text__icontains=s)|Q(raw_description__icontains=s))
        if p.get('search'):
            s=p['search']; qs=qs.filter(Q(company__icontains=s)|Q(title__icontains=s)|Q(original_source_text__icontains=s)|Q(raw_description__icontains=s)|Q(url__icontains=s))
        if p.get('analyzed') in ('1','true','yes'):
            qs=qs.filter(evaluations__isnull=False)
        if p.get('board') in ('1','true','yes'):
            qs=qs.exclude(Q(title='')|Q(title__istartswith='Untitled role'))
        today=timezone.localdate()
        # TASK-145 AC4: an absent ?ordering= -- the key missing from the request entirely, distinct
        # from an explicit ?ordering= that is empty or hostile (those already resolve to the default
        # via parse_board_ordering's own '(raw or '').split(',')' fallback, and an explicit param must
        # win over the saved one regardless of what it resolves to) -- reads the user's saved
        # board_sort_keys instead of jumping straight to DEFAULT_BOARD_ORDERING. The profile value is
        # handed to the exact same parse_board_ordering() below as a typed ?ordering= value -- same
        # allowlist, same 3-key cap, same degrade-on-hostile-input -- so there is no second parser to
        # keep in sync with the one that already guards against ?ordering=-created_by__password.
        raw_ordering=p.get('ordering')
        if raw_ordering is None:
            profile=getattr(self.request.user, 'jobradar_profile', None)
            raw_ordering=profile.board_sort_keys if profile else ''
        qs=qs.annotate(
            # -1 surfaces, 1 sinks. One expression owns every age/deadline signal on the board.
            stale_rank=Case(
                When(status__in=JobLead.UNAPPLIED_STATUSES, apply_by__lte=today+timezone.timedelta(days=JobLead.DEADLINE_SOON_DAYS), then=Value(-1)),
                When(status__in=JobLead.DATED_STATUSES, status_date__lt=today-timezone.timedelta(days=JobLead.STALE_APPLIED_DAYS), then=Value(1)),
                When(status__in=JobLead.UNAPPLIED_STATUSES, created_at__lt=timezone.now()-timezone.timedelta(days=JobLead.STALE_UNAPPLIED_DAYS), then=Value(1)),
                default=Value(0), output_field=IntegerField()),
            # TASK-145 AC1/AC2: the default board GROUP order -- see _attention_rank's own docstring.
            attention_rank=_attention_rank(),
            priority_rank=Case(When(evaluations__priority='high', then=Value(0)), When(evaluations__priority='medium', then=Value(1)), When(evaluations__priority='low', then=Value(2)), default=Value(3), output_field=IntegerField()),
            # TASK-108: pipeline order for ordering=status, distinct from status_rank's attention
            # order above -- see BOARD_ORDERINGS' comment.
            status_pipeline_rank=_status_pipeline_rank(),
            # TASK-126 AC4: recorded decision -- option 1 from the task notes. A boolean Exists()
            # subquery rather than a Count(): this queryset already joins/filters through
            # `evaluations` and ends in .distinct(), so a Count() on a second reverse relation would
            # fan out with that join and need its own distinct-count gymnastics for a value this view
            # only ever treats as true/false. Exists() never joins, so it costs nothing beyond one
            # correlated subquery per row and is exposed only on JobLeadListSerializer (the /jobs/
            # list), never widening the detail response.
            has_mailbox_history=Exists(MailboxMessage.objects.filter(matched_job=OuterRef('pk'))),
        ).order_by(*parse_board_ordering(raw_ordering))
        return qs.distinct()
    def list(self, request, *args, **kwargs):
        response=super().list(request, *args, **kwargs)
        handed_off=set(submitted_away_jobs(request.user).values_list('id', flat=True))
        if handed_off:
            response.data=[submission_row(row) if row['id'] in handed_off else row for row in response.data]
        return response
    def create(self, request, *args, **kwargs):
        ser=self.get_serializer(data=request.data); ser.is_valid(raise_exception=True)
        url=ser.validated_data.get('url')
        action=request.data.get('duplicate_action')
        existing=find_existing_by_url(url, queryset=accessible_jobs(request.user))
        if existing and not action:
            return Response({'ok':False,'type':'duplicate_conflicts','message':'This job link already exists.','conflicts':[{'index':0,'url':url,'incoming':{'company':ser.validated_data.get('company') or 'Unknown company','title':ser.validated_data.get('title') or 'Untitled role'},'existing_jobs':[JobLeadSerializer(existing).data]}]}, status=400)
        if existing and action=='override':
            replace_job_with_supplied_data(existing, ser.validated_data, request.user)
            return Response(JobLeadSerializer(existing).data)
        if existing and action=='duplicate':
            ser.validated_data['title']=duplicate_title(ser.validated_data.get('title') or 'Untitled role', accessible_jobs(request.user))
        if existing and action=='skip': return Response(JobLeadSerializer(existing).data)
        obj=ser.save(**job_create_defaults(request.user)); return Response(JobLeadSerializer(obj).data, status=201)
    def perform_create(self, serializer): serializer.save(**job_create_defaults(self.request.user))
    @action(detail=True, methods=['patch'], url_path='source-text')
    def source_text(self, request, pk=None):
        job=self.get_object()
        text=(request.data.get('original_source_text') or '').strip()
        if not JobLead.is_meaningful_source(text):
            return Response({'detail':'Original job text must contain the job description, not only a link.'}, status=400)
        JobLead.objects.filter(pk=job.pk).update(original_source_text=text)
        return Response({'original_source_text':text})
    def destroy(self, request, pk=None):
        qs=accessible_jobs(request.user)
        try:
            job=qs.get(pk=pk)
        except JobLead.DoesNotExist:
            return Response({'detail':'Not found'}, status=404)
        if job.status != 'archived':
            return Response({'detail':'Only archived jobs can be permanently deleted'}, status=400)
        job.delete()
        return Response(status=204)
    @action(detail=True, methods=['get','post'])
    def evaluations(self, request, pk=None):
        job=self.get_object()
        if request.method=='GET': return Response(JobEvaluationSerializer(job.evaluations.all(), many=True).data)
        ser=JobEvaluationSerializer(data={**request.data, 'job': job.id}, context={'request': request}); ser.is_valid(raise_exception=True); ser.save(); return Response(ser.data, status=201)
    @action(detail=True, methods=['get','post'])
    def notes(self, request, pk=None):
        job=self.get_object()
        if request.method=='GET': return Response(ApplicationNoteSerializer(job.notes.all(), many=True).data)
        ser=ApplicationNoteSerializer(data={**request.data,'job':job.id}, context={'request': request}); ser.is_valid(raise_exception=True); ser.save(created_by=request.user); return Response(ser.data, status=201)
    @action(detail=True, methods=['get','post'])
    def followups(self, request, pk=None):
        job=self.get_object()
        if request.method=='GET': return Response(FollowUpSerializer(job.followups.all(), many=True).data)
        ser=FollowUpSerializer(data={**request.data,'job':job.id}, context={'request': request}); ser.is_valid(raise_exception=True); ser.save(); return Response(ser.data, status=201)
    @action(detail=True, methods=['get'])
    def mailbox(self, request, pk=None):
        """TASK-117 AC2 / TASK-120 AC1,AC3,AC4,AC5: every mailbox message matched to this job --
        not only the ones with a pending suggestion -- plus the job's own ApplicationNotes, in one
        response so the client needs no second round trip for the notes half of the decision view.
        This is a flat per-job list, not a reconstructed thread: MailboxMessage has no parent-message
        pointer to chain on (RawMessage.references is transient and Gmail's threadId was dropped
        until TASK-121 persisted it), so grouping messages into real conversations is not attempted
        here -- see TASK-120's task notes. self.get_object() runs against get_queryset()
        (accessible_jobs) exactly like every other detail action above -- a job this user cannot see
        404s before any message or note is read (TASK-120 AC6).

        TASK-143 AC4/AC6: deliberately NOT filtered by JobLead.ACTIONABLE_STATUSES -- this is the
        named place a message matched to a non-actionable (e.g. rejected) job stays fully visible.
        MailboxSuggestionViewSet.list below hides that job's conversation from the review PANEL;
        nothing here erases it from the job's own detail view.
        """
        job=self.get_object()
        # TASK-120 AC2: MailboxMessage.Meta.ordering ('-uid') is wrong for this view -- for
        # Gmail-API rows uid is a locally-assigned sequence number minted in processing order (see
        # that model's docstring), not a received time. received_at is nullable (rows written before
        # it existed, or any transport hiccup that left it unset); nulls_last is a deliberate choice
        # over the default arbitrary placement -- "we don't know when this arrived" reads closer to
        # "oldest" than "newest" in a newest-first decision list.
        messages=job.mailbox_messages.select_related('matched_job').prefetch_related('draft','suggestions').order_by(F('received_at').desc(nulls_last=True))
        # One extra query for a single job instance -- not the N+1 that prefetch_related guards
        # against for a list of parents -- same pattern as the sibling `notes` action above.
        # ApplicationNote.Meta.ordering is already ['-created_at'], so this is newest first (AC3).
        notes=job.notes.all()
        return Response({
            'messages': MailboxMessageWithSuggestionsSerializer(messages, many=True).data,
            'notes': ApplicationNoteSerializer(notes, many=True).data,
        })
    @action(detail=False, methods=['get'], url_path='feedback-due')
    def feedback_due(self, request):
        """TASK-146 AC1/AC2/AC8: the feedback-deadline pane's one query -- every actionable job
        that carries a feedback_due_date, oldest date first. A single ascending sort by
        feedback_due_date does both of AC1/AC2's asks in one expression: overdue rows (date <
        today) sort before upcoming ones because their dates are chronologically earlier, and
        within each side of that boundary the same ascending order reads as "most overdue first"
        and "soonest first" respectively -- so the job overdue by 23 days leads the overdue group
        instead of sorting as if it were barely due (AC2). `overdue` is computed in Python, not a
        second query, from `today` and each row's own date.

        AC8: reuses JobLead.ACTIONABLE_STATUSES, the one place this split is defined (see that
        constant's own comment), rather than a second literal status list -- a rejected/withdrawn/
        skipped/archived job never appears here, same rule TASK-143's mailbox review panel follows.

        AC10: one query. `.values()` selects only JobLead's own columns (no join, no
        prefetch_related, no evaluations touched) so the response costs exactly one SELECT
        regardless of how many rows come back -- no per-row query for company/title/status/date,
        all of which already live on this table.
        """
        today=timezone.localdate()
        rows=accessible_jobs(request.user).filter(
            status__in=JobLead.ACTIONABLE_STATUSES,
            feedback_due_date__isnull=False,
        ).order_by('feedback_due_date', 'id').values('id', 'company', 'title', 'status', 'feedback_due_date')
        return Response([{**row, 'overdue': row['feedback_due_date'] < today} for row in rows])

class EvaluationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class=JobEvaluationSerializer; queryset=JobEvaluation.objects.select_related('job').all()
    def get_queryset(self): return JobEvaluation.objects.select_related('job').filter(job__in=accessible_jobs(self.request.user))
    def partial_update(self, request, pk=None):
        evaluation=self.get_object()
        ser=self.get_serializer(evaluation, data=request.data, partial=True)
        ser.is_valid(raise_exception=True); ser.save()
        return Response(ser.data)

class NoteViewSet(viewsets.GenericViewSet):
    serializer_class=ApplicationNoteSerializer; queryset=ApplicationNote.objects.all()
    def get_queryset(self): return ApplicationNote.objects.select_related('job').filter(job__in=accessible_jobs(self.request.user))
    def partial_update(self, request, pk=None):
        note=self.get_object()
        ser=ApplicationNoteSerializer(note, data=request.data, partial=True, context={'request': request})
        ser.is_valid(raise_exception=True); ser.save()
        return Response(ser.data)
    def destroy(self, request, pk=None): self.get_object().delete(); return Response(status=204)

class FollowUpViewSet(viewsets.ModelViewSet):
    serializer_class=FollowUpSerializer; queryset=FollowUp.objects.select_related('job').all()
    http_method_names=['get','patch','head','options']
    def get_queryset(self): return FollowUp.objects.select_related('job').filter(job__in=accessible_jobs(self.request.user))

class MailboxSuggestionViewSet(viewsets.GenericViewSet):
    """TASK-109 AC3. List defaults to pending (?status=confirmed,dismissed to see decided ones);
    confirm/dismiss are the only two mutations, and both refuse an already-decided suggestion
    rather than silently re-applying or re-dismissing it.
    """
    serializer_class=MailboxSuggestionSerializer
    def get_queryset(self):
        return MailboxSuggestion.objects.select_related('job','message','message__matched_job').filter(job__in=accessible_jobs(self.request.user))
    def list(self, request, *args, **kwargs):
        qs=self.get_queryset()
        statuses=[s for s in (request.query_params.get('status') or 'pending').split(',') if s]
        if statuses: qs=qs.filter(status__in=statuses)
        # TASK-143 AC2/AC5/AC7: this is the mailbox review panel's own feed (the frontend builds one
        # JobMailboxConversationCard per job that shows up here), so a job the owner has already
        # closed out (rejected/withdrawn/skipped/archived) is filtered OUT here -- job 760
        # (Deltia AI, rejected) disappears from the panel this way. Deliberately only here, not in
        # get_queryset() above: confirm/dismiss keep working on a suggestion reached some other way
        # (e.g. from the job's own detail view, TASK-143 AC4/AC6), so an existing pending suggestion
        # on a now-excluded job is HIDDEN, never dismissed or deleted (AC7 -- there are 4 of those in
        # production today, and this is the "left pending but hidden" choice, the least destructive
        # of the three the task names). Because this filters on the job's live `status` rather than a
        # stored flag, moving the job back to an actionable status brings it back on the very next
        # load, with no re-fetch or repair (AC5).
        qs=qs.filter(job__status__in=JobLead.ACTIONABLE_STATUSES)
        return Response(self.get_serializer(qs, many=True).data)
    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        suggestion=self.get_object()
        if suggestion.status != 'pending': return Response({'detail':'Suggestion already decided.'}, status=400)
        # TASK-117 AC4: apply_suggestion writes the confirming user onto the ApplicationNote it
        # creates, so the job's history says who agreed, not only that the app proposed it.
        apply_suggestion(suggestion, user=request.user)
        return Response(self.get_serializer(suggestion).data)
    @action(detail=True, methods=['post'])
    def dismiss(self, request, pk=None):
        suggestion=self.get_object()
        if suggestion.status != 'pending': return Response({'detail':'Suggestion already decided.'}, status=400)
        dismiss_suggestion(suggestion)
        return Response(self.get_serializer(suggestion).data)

def is_mailbox_owner(user):
    """TASK-151 AC1: the gate every MAILBOX endpoint below uses -- deliberately NOT is_cv_owner.

    is_cv_owner is gated on settings.CODEX_CV_ENABLED, a deployment-time kill switch for whether
    the CV subsystem can run on THIS server (env_bool('CODEX_CV_ENABLED', DEBUG), False whenever
    DEBUG is False). That is correct for CV generation, which genuinely cannot run in the deployed
    container -- but it made is_cv_owner return False for the owner's own account on the deployed
    site even though the account itself never changed, hiding mailbox endpoints that have nothing
    to do with the CV subsystem and work fine there. Mailbox ownership is a property of the
    ACCOUNT in the shared database, not of the server answering the request, so it needs a
    predicate that reads the same on every deployment of that one database: `is_staff` is a plain
    boolean column on auth_user, not an env var, so it cannot diverge between deployments the way
    CODEX_CV_ENABLED does. On the production database exactly 1 of 9 accounts is staff (the
    owner).
    """
    return bool(user and user.is_authenticated and user.is_staff)


class MailboxRunViewSet(viewsets.ReadOnlyModelViewSet):
    """TASK-109 AC4. Runs are not per-job, so accessible_jobs scoping does not apply -- gated on
    is_mailbox_owner instead (TASK-151: switched from is_cv_owner, which was unreachable on the
    deployed site -- see is_mailbox_owner's docstring), since this is inherently a personal-mailbox
    audit trail rather than shared board data.
    """
    serializer_class=MailboxRunSerializer
    def get_queryset(self):
        if not is_mailbox_owner(self.request.user): return MailboxRun.objects.none()
        return MailboxRun.objects.all().prefetch_related('messages__matched_job','messages__draft')
    @action(detail=False, methods=['post'], url_path='run-now')
    def run_now(self, request):
        """TASK-124 AC1/AC2/AC9: same owner gate as the rest of this viewset -- this triggers real
        mailbox access, so it is never reachable by anyone else. Delegates entirely to
        services.mailbox_tasks.start_mailbox_check, which already decides start-now-on-a-thread vs
        queue-a-request from has_mailbox_credentials() (services.mailbox._default_transport()) --
        this view adds no second capability check of its own. Returns immediately either way
        (AC1): 'queued' tells the client which case it got, matching the {'queued', 'task_id'} /
        {'queued', 'request_id'} shapes start_mailbox_check documents.
        """
        if not is_mailbox_owner(request.user):
            return Response({'detail': 'Not found.'}, status=404)
        return Response(mailbox_tasks.start_mailbox_check(request.user))
    @action(detail=False, methods=['get'], url_path='status')
    def status_view(self, request):
        """TASK-124 AC5/AC6/AC7/AC8: one endpoint to poll regardless of how the run was triggered
        (this app's own thread, a queued request picked up on the owner's machine, or a plain
        `manage.py check_mailbox` on the command line) -- mailbox.current_mailbox_run() is the one
        row AC4's concurrency guard allows to be "in progress" at a time, so there is nothing to
        disambiguate between triggers here.

        `run` is the in-progress run while one exists, otherwise the most recently attempted one
        (AC6: the outcome -- counters or error -- must still be visible without a manual refresh).
        `estimate` is mailbox.mailbox_check_estimate() verbatim (AC7: None with no history of that
        kind, never an invented number). `taking_longer_than_usual` is computed here, not left for
        the client to derive, so a missing estimate or an instant run can never read as a negative
        countdown (AC8).
        """
        if not is_mailbox_owner(request.user):
            return Response({'detail': 'Not found.'}, status=404)
        run = mailbox.current_mailbox_run() or MailboxRun.objects.first()
        running = bool(run and run.finished_at is None)
        elapsed_seconds = (timezone.now() - run.started_at).total_seconds() if running else None
        estimate = mailbox.mailbox_check_estimate()
        estimated_seconds = estimate.get('estimated_seconds')
        taking_longer_than_usual = bool(running and estimated_seconds is not None and elapsed_seconds > estimated_seconds)
        return Response({
            'has_credentials': mailbox.has_mailbox_credentials(),
            'running': running,
            'run': MailboxRunSerializer(run).data if run else None,
            'elapsed_seconds': elapsed_seconds,
            'estimate': estimate,
            'taking_longer_than_usual': taking_longer_than_usual,
        })
    @action(detail=False, methods=['get'], url_path='calendars')
    def calendars_view(self, request):
        """TASK-116 AC2: the calendars the Gmail OAuth token can see, for the settings-page picker --
        the owner selects by name FROM this list; no URL is ever typed or pasted. Same is_mailbox_owner
        gate as the rest of this viewset.

        Always 200: an unconfigured or expired/revoked OAuth client is a normal, expected state here
        (see docs/email-setup.md), not a server error, so this never raises to the client -- it
        reports `error` instead, for the picker to show in place of the (then-empty) calendar list.
        Response shape: {'calendars': [{'id': str, 'summary': str}, ...], 'error': str}.
        """
        if not is_mailbox_owner(request.user):
            return Response({'detail': 'Not found.'}, status=404)
        if not (settings.GMAIL_OAUTH_CLIENT_ID and settings.GMAIL_OAUTH_CLIENT_SECRET):
            return Response({'calendars': [], 'error': 'Gmail OAuth is not configured on this server.'})
        try:
            calendars = mailbox.list_calendars(settings.GMAIL_OAUTH_CLIENT_ID, settings.GMAIL_OAUTH_CLIENT_SECRET, settings.GMAIL_OAUTH_TOKEN_PATH)
        except Exception as exc:
            return Response({'calendars': [], 'error': str(exc)})
        return Response({'calendars': calendars, 'error': ''})

class MailboxMessageViewSet(viewsets.GenericViewSet):
    """TASK-117 AC6/AC7. MailboxMessage.uid is globally unique with no user FK -- the mailbox
    subsystem is single-owner by construction, so this is gated on is_mailbox_owner exactly like
    MailboxRunViewSet above (TASK-151: switched from is_cv_owner -- see is_mailbox_owner's
    docstring), not on accessible_jobs. Exposes only what AC6 needs (the unmatched list
    and the manual attach action), TASK-142's `retrieve` (the full-body counterpart to unmatched's
    truncated preview -- see MailboxMessageListSerializer), TASK-171's dismiss/undismiss (the OTHER
    honest ending for an unmatched message, alongside attach), plus TASK-133's reply-recipients preview
    and reply-compose actions below -- still never list/PATCH/DELETE, keeping the model's append-only
    guarantee true for everything except the two owner-initiated single-field mutations (matched_job,
    dismissed_at -- see the model docstring). Composing a reply never mutates MailboxMessage itself
    either -- it only ever creates/updates the message's MailboxDraft row (see
    services.mailbox.compose_reply_draft), the same append-only-except-those-fields shape attach and
    dismiss already hold.

    reply_recipients/reply are deliberately scoped through accessible_jobs (like MailboxDraftViewSet
    below), not the is_mailbox_owner gate the rest of this viewset uses -- see each action's own
    docstring.
    """
    serializer_class=MailboxMessageSerializer
    def get_queryset(self):
        if not is_mailbox_owner(self.request.user): return MailboxMessage.objects.none()
        return MailboxMessage.objects.all()
    def retrieve(self, request, pk=None):
        """TASK-142 AC1/AC5/AC7 support: `unmatched` below truncates body_text to a preview
        (MailboxMessageListSerializer) so the list itself stays bounded -- this is where the owner
        gets the FULL message, including its complete body and any pending suggestions, when a row
        is actually opened. Same is_mailbox_owner gate as the rest of this viewset (an unmatched
        message has no matched_job to scope through accessible_jobs the way _accessible_message
        below does).
        Nothing is deleted or unreachable by bounding the list (AC7): every message still has exactly
        one extra request between it and being fully readable.
        """
        message=self.get_object()
        return Response(MailboxMessageWithSuggestionsSerializer(message).data)
    @action(detail=False, methods=['get'])
    def unmatched(self, request):
        # TASK-142 AC2, round 1 (coordinator re-measurement, 2026-08-19): truncating in
        # MailboxMessageListSerializer.to_representation() was NOT enough -- Django had already
        # pulled every row's FULL body_text off the wire (Neon, not local sqlite) before that Python
        # code ever ran, so 836 messages x ~2,354 chars still cost the same ~2MB transfer regardless
        # of what the serializer did with it afterwards. The truncation has to happen in the SQL:
        # .defer('body_text') drops the full column from the SELECT list, and the Substr annotation
        # computes a BOUNDED (PREVIEW_CHARS+1)-char preview in the database instead -- the +1 is so
        # the serializer can tell "was this the whole body" apart from "was this truncated" without a
        # second COUNT/LENGTH query. MailboxMessageListSerializer reads body_preview, never
        # instance.body_text (touching the deferred field would silently trigger one reload query
        # PER ROW, reintroducing the exact cost this removes).
        #
        # TASK-142 AC2, round 2 (coordinator re-measurement, 2026-08-19): the payload was fixed
        # (408KB, well under a second) but wall-clock was not -- 320 queries against Neon (~38ms
        # each) for 319 rows, all but one of them `SELECT ... FROM mailboxdraft WHERE message_id=?`,
        # one per row. `draft` is a REVERSE one-to-one (MailboxDraft.message), so DRF fetches it lazily
        # per instance unless the query already joined it. select_related('draft') -- not
        # prefetch_related, which would still be 2 queries but the wrong fix for a reverse
        # one-to-one -- pulls it in the SAME query via a LEFT OUTER JOIN.
        #
        # Considered dropping `draft` from this serializer instead (an unmatched message has no
        # matched_job, and a draft is only ever written for a matched one -- see
        # maybe_draft_reply()'s `if matched is not None` gate and compose_reply_draft()'s
        # accessible_jobs scoping in this same file, both in services.mailbox/views.py). Checked
        # rather than assumed: TASK-129/TASK-137's historical detach_job_board_messages()/
        # detach_ats_host_messages() clear `matched_job` back to None WITHOUT touching an already-
        # written MailboxDraft, so a message can be unmatched today with a real draft still attached
        # -- confirmed against production (DACHAPPLY_ALLOW_PROD_DB=1, read-only): 107 of 836 unmatched
        # messages carry one. Dropping the field would silently hide 107 real Gmail Drafts the owner
        # already has open, which is worse than the 12s this join removes -- select_related is the
        # correct fix, not a shortcut around checking.
        #
        # matched_job_company/matched_job_title (source='matched_job.company'/'.title' on the base
        # MailboxMessageSerializer) do NOT need the same treatment: matched_job__isnull=True in this
        # queryset means matched_job_id is NULL on every row, and Django's forward-FK descriptor
        # returns None from that WITHOUT a query when the id itself is None -- no join needed here,
        # though that is this endpoint's own filter guaranteeing it, not a property of the serializer,
        # so it would need revisiting if this serializer is ever reused without that filter.
        #
        # TASK-161: `-uid` alone buried the 41 currently-unattached rejections/interview invitations
        # among 280 messages attaching can mostly do nothing with (task-161's Implementation Notes).
        # `rank` is a Case/When computed HERE, in the query, not in Python or the browser (AC2) --
        # UNMATCHED_HIGH_CONSEQUENCE_CLASSIFICATIONS first, UNMATCHED_LOW_CONSEQUENCE_CLASSIFICATIONS
        # second, everything else (including 'offer', which the task's rank spec never names) last --
        # and order_by sorts on that annotation, then most-recent-first, with `-uid` kept as the final
        # tiebreak so ordering stays deterministic when received_at is null or two rows tie (AC1).
        #
        # `F('received_at').desc(nulls_last=True)` rather than a plain `-received_at`, and the reason
        # is a divergence the test suite CANNOT catch: Postgres (Neon, production) defaults DESC to
        # NULLS FIRST, so a row with no received_at would sort as though it were the newest in its
        # rank bucket -- the opposite of most-recent-first -- while sqlite (the hermetic test DB)
        # sorts nulls lowest and puts them last, so a green suite proves nothing here. Measured
        # 2026-08-21: 0 of the 321 current panel rows have a null received_at, so this is latent
        # rather than live, but it is one expression and the same idiom line 815 already uses.
        #
        # The recency window (UNMATCHED_RECENCY_WINDOW_DAYS) applies ONLY to rank 1/2 -- rank 0 rows
        # are never age-filtered, because 15 of the 41 high-signal rows measured against production are
        # themselves over a year old; filtering them by age would hide the exact rows this endpoint
        # exists to surface (AC3/AC4). A row with no received_at at all counts as visible rather than
        # guessed old -- there is no measured age to filter it by. hidden_count is a second, cheap
        # COUNT(*) query (never selects body_text -- see
        # test_unmatched_messages_query_defers_body_text_and_computes_a_bounded_db_side_preview) run
        # only when the filter is actually applied, so the UI can state what `?include_older=1` -- which
        # skips the filter and this query entirely -- would add back, rather than silently dropping it.
        preview_len = MailboxMessageListSerializer.BODY_PREVIEW_CHARS + 1
        include_older = str(request.query_params.get('include_older') or '').strip().lower() in ('1', 'true', 'yes')
        # TASK-163 AC5: a second, independent reveal -- same query-param naming as include_older --
        # for rows whose subject/body names no tracked company at all (no `suggested_job` below).
        # Applied AFTER the recency filter, on whatever this request would otherwise have shown, the
        # same "second, cheap dimension stacked on the first" shape include_older already has.
        include_unidentified = str(request.query_params.get('include_unidentified') or '').strip().lower() in ('1', 'true', 'yes')
        # TASK-171 AC3/AC4: a third, independent reveal, same shape again -- a message the owner
        # dismissed ("not attachable to any job") is excluded from the base queryset entirely (not
        # merely display-filtered like the two above), so it never reaches the rank/suggestion work
        # below at all unless this is set.
        include_dismissed = str(request.query_params.get('include_dismissed') or '').strip().lower() in ('1', 'true', 'yes')
        base_qs = self.get_queryset().exclude(classification='not_job_related').filter(matched_job__isnull=True)
        dismissed_count = 0
        if not include_dismissed:
            dismissed_count = base_qs.filter(dismissed_at__isnull=False).count()
            base_qs = base_qs.filter(dismissed_at__isnull=True)
        qs=(base_qs
            .select_related('draft')
            .annotate(body_preview=Substr('body_text', 1, preview_len))
            .annotate(match_text=Substr('body_text', 1, UNMATCHED_MATCH_TEXT_CHARS))
            .defer('body_text')
            .annotate(rank=Case(
                When(classification__in=UNMATCHED_HIGH_CONSEQUENCE_CLASSIFICATIONS, then=Value(0)),
                When(classification__in=UNMATCHED_LOW_CONSEQUENCE_CLASSIFICATIONS, then=Value(1)),
                default=Value(2), output_field=IntegerField(),
            ))
            .order_by('rank', F('received_at').desc(nulls_last=True), '-uid'))

        # TASK-169: the per-account identification window is now the ACTIVE cutoff --
        # UNMATCHED_RECENCY_WINDOW_DAYS above only supplies its default (see _identify_window's own
        # comment). `window_explicit` is AC7's whole point: a DEFAULT window stays display-only for
        # rank 0 (never filters it, exactly as TASK-161 shipped -- 15 of 41 high-consequence rows are
        # themselves over a year old), while an EXPLICIT one also bounds rank 0, with its own
        # separately-reported, revealable count (high_consequence_hidden_count) rather than folding
        # into hidden_count, which stays rank-1/2-only either way.
        profile = user_profile_settings(request.user)
        window_days, window_explicit = _identify_window(profile)
        cutoff = timezone.now() - timezone.timedelta(days=window_days)
        within_window = Q(received_at__isnull=True) | Q(received_at__gte=cutoff)

        hidden_count = 0
        high_consequence_hidden_count = 0
        if not include_older:
            low_consequence_visible = Q(rank=0) | within_window
            hidden_count = qs.exclude(low_consequence_visible).count()
            if window_explicit:
                high_consequence_hidden_count = qs.filter(rank=0).exclude(within_window).count()
                qs = qs.filter(within_window)
            else:
                qs = qs.filter(low_consequence_visible)

        # TASK-163 AC1/AC3/AC5/AC9: suggest the single tracked job named in each row's own
        # subject/body(/sender) -- never matched_job (attach_message_to_job is still the only writer
        # of that field). `jobs` is ONE bulk query for the owner's whole tracked-job list, fetched
        # here rather than inside suggest_job_for_message, so scoring every row below costs zero extra
        # queries -- the same per-row-query trap TASK-142's select_related('draft') already fixed for
        # `draft`. `row.match_text` (the SECOND, wider Substr(...) annotation above -- see
        # UNMATCHED_MATCH_TEXT_CHARS' comment) is what gets scored, never row.body_text -- that column
        # is still .defer()'d, so touching it would silently trigger one reload query PER ROW, exactly
        # the regression TASK-142 removed for this endpoint.
        jobs = list(owned_jobs(request.user).exclude(company=''))
        # TASK-170: the timing evidence that separates two tracked jobs at the SAME company -- job id
        # -> the earliest date the owner's OWN mail on that job's thread was sent, which is what
        # actually dates an application (sent_by_owner, stored since TASK-132; run_check only ever
        # stores a sent message when its thread already belongs to a tracked job, so a row here is
        # always the owner writing to that job's process). ONE bulk aggregate for the whole list, in
        # the same style and for the same reason as `jobs` above -- per-row queries on this endpoint
        # are the regression TASK-142 already paid to remove. `.order_by()` is load-bearing, not
        # tidying: MailboxMessage.Meta.ordering ('-uid') would otherwise be added to the GROUP BY and
        # return one row per message instead of one per job.
        #
        # `received_at >= matched_job.created_at` is what makes the evidence trustworthy rather than
        # merely present, measured against production (coordinator, 2026-08-23): of the 11 jobs with
        # sent mail, SIX had a first-sent date BEFORE the job existed at all, by 238 to 685 days (job
        # 462 is the 685) -- old correspondence with that company swept onto the thread by matching,
        # which as a process start date is not just wrong but wrong in the direction that loses,
        # dragging a real 2026 process back into 2024 and handing the window rule a fabricated
        # ordering. Bounding it costs 3 of the 11 (coverage 11 -> 8) and is a straight trade for the
        # 6 corrupt ones; _process_started_at's three job-date sources more than cover the loss. Still
        # ONE query -- an F() comparison is a JOIN in the same statement, not a second round trip.
        first_sent_at = dict(MailboxMessage.objects
                             .filter(sent_by_owner=True, matched_job__in=jobs, received_at__isnull=False,
                                     received_at__gte=F('matched_job__created_at'))
                             .values_list('matched_job').annotate(Min('received_at')).order_by())
        rows = list(qs)
        for row in rows:
            # TASK-169 AC6: the identification ATTEMPT is what the window bounds, not just what gets
            # displayed -- a row outside the window never reaches suggest_job_for_message at all,
            # whatever include_older says (revealing an old row shows it; it does not retroactively
            # pay for guessing a job for it). No received_at at all counts as within the window, the
            # same "no measured age to filter by" rule the display filter above already applies.
            if row.received_at is not None and row.received_at < cutoff:
                row.suggested_job = None
            else:
                row.suggested_job = suggest_job_for_message(row.subject, row.match_text, row.sender, jobs, row.received_at, first_sent_at)
        # TASK-163 fix 3 (coordinator re-measurement, 2026-08-21): parking every suggestion-less row
        # hid 38 of TASK-161's 41 high-consequence rows -- rank 0 (rejection/interview_invitation) is
        # never age-filtered by the recency window above for exactly the same reason it must never be
        # PARKED here either: attaching one can always act, suggestion or not, so hiding it behind
        # "no suggestion" reverses the whole point of TASK-161 shipping it to the top of the list.
        # Only rank 1/2 (the low-consequence/uncertain classes) are parked when they carry no
        # suggestion -- the same asymmetry the recency window already applies, for the same reason.
        parked_count = 0
        if not include_unidentified:
            parked_count = sum(1 for row in rows if row.suggested_job is None and row.rank != 0)
            rows = [row for row in rows if row.suggested_job is not None or row.rank == 0]
        return Response({
            'results': MailboxMessageListSerializer(rows, many=True).data,
            'hidden_count': hidden_count,
            'high_consequence_hidden_count': high_consequence_hidden_count,
            'parked_count': parked_count,
            'dismissed_count': dismissed_count,
        })
    @action(detail=True, methods=['post'])
    def attach(self, request, pk=None):
        """TASK-117 AC6: the only writer of `matched_job` for a message that already ran through
        check_mailbox -- everything else about MailboxMessage stays append-only. self.get_object()
        already applies the is_mailbox_owner gate via get_queryset(); the target job additionally
        has to be one this user can already see (accessible_jobs), or it 404s the same way reading
        that job would. Re-attaching to the SAME job is a no-op (attach_message_to_job is
        idempotent); attaching to a DIFFERENT job than the one already matched is refused rather
        than silently re-pointing the message.
        """
        message=self.get_object()
        job_id=request.data.get('job')
        if not job_id:
            return Response({'detail':'job is required.'}, status=400)
        job=accessible_jobs(request.user).filter(pk=job_id).first()
        if not job:
            return Response({'detail':'Job not found.'}, status=404)
        if message.matched_job_id and message.matched_job_id != job.id:
            return Response({'detail':'This message is already attached to a different job.'}, status=400)
        attach_message_to_job(message, job, user=request.user)
        message.refresh_from_db()
        return Response(MailboxMessageWithSuggestionsSerializer(message).data)

    @action(detail=True, methods=['post'])
    def dismiss(self, request, pk=None):
        """TASK-171 AC3/AC5/AC6: marks a message "not attachable to any job" -- excluded from
        `unmatched`'s default results from the very next load on (AC3), reversible via `undismiss`
        below (AC4). Writes NEITHER matched_job NOR a suggestion (AC5): attach_message_to_job remains
        the only path that does either, so this can never be mistaken for (or reimplemented as)
        attaching to a placeholder job, which would put a fake lead on the board and feed the stats.
        Idempotent -- dismissing an already-dismissed message leaves its original dismissed_at alone.
        """
        message=self.get_object()
        if message.dismissed_at is None:
            message.dismissed_at=timezone.now()
            message.save(update_fields=['dismissed_at'])
        return Response(MailboxMessageListSerializer(message).data)

    @action(detail=True, methods=['post'])
    def undismiss(self, request, pk=None):
        """TASK-171 AC4: the reversal -- clears dismissed_at so the message is a normal unmatched row
        again on the very next load, the same "reversible, never destructive" shape TASK-161's
        include_older and TASK-163's include_unidentified reveals already hold to (neither of those
        deletes anything either; they only stop filtering it out).
        """
        message=self.get_object()
        if message.dismissed_at is not None:
            message.dismissed_at=None
            message.save(update_fields=['dismissed_at'])
        return Response(MailboxMessageListSerializer(message).data)

    def _accessible_message(self, request, pk):
        """TASK-133: reply-recipients/reply write into and read from the OWNER's real mailbox, so
        this is deliberately not self.get_object() (which routes through get_queryset()'s
        is_mailbox_owner gate above) -- it is scoped through the message's own matched_job via
        accessible_jobs, the same rule every other job-linked resource in this app already uses
        (MailboxDraftViewSet.get_queryset(), JobLeadViewSet, ...). A second user who cannot see the
        matched job gets 404 here exactly as they would reading that job's own mailbox panel,
        regardless of whether they are the mailbox owner (is_mailbox_owner).
        """
        return MailboxMessage.objects.filter(pk=pk, matched_job__in=accessible_jobs(request.user)).first()

    @action(detail=True, methods=['get'], url_path='reply-recipients')
    def reply_recipients(self, request, pk=None):
        """TASK-133 AC2/AC3: read-only preview of who a reply or reply-all would go to, BEFORE
        anything is written -- derived from the message's own headers (mailbox.derive_reply_recipients),
        never guessed. `reply` below writes exactly the list the owner confirms here, so this preview
        and what gets saved must come from the same derivation to keep AC3's "shown verbatim" true.
        """
        message = self._accessible_message(request, pk)
        if not message:
            return Response({'detail': 'Not found.'}, status=404)
        reply_all = str(request.query_params.get('reply_all') or '').strip().lower() in ('1', 'true', 'yes')
        return Response(mailbox.derive_reply_recipients(message, reply_all))

    @action(detail=True, methods=['post'])
    def reply(self, request, pk=None):
        """TASK-133 AC2/AC3/AC6/AC8: compose a hand-edited reply and save it into Gmail Drafts on
        this message's thread.

        `to`/`cc` are taken from the request EXACTLY as sent -- never re-derived here and silently
        substituted, or reply_recipients' preview above would not be what actually gets saved (AC3).
        Malformed addresses are rejected before compose_reply_draft ever runs (AC7's "a recipient the
        owner did not intend cannot be introduced silently" starts with "cannot be a typo either").

        compose_reply_draft runs check_guardrails on the composed text exactly as maybe_draft_reply
        does for a generated draft (AC6), and returns '' on success or a short refusal reason
        otherwise -- never raises -- so a Gmail rejection or a guardrail block is a 4xx with the
        reason and nothing half-written (AC8), the same contract update_draft_text already holds.
        """
        message = self._accessible_message(request, pk)
        if not message:
            return Response({'detail': 'Not found.'}, status=404)
        body_text = (request.data.get('body_text') or '').strip()
        raw_to = request.data.get('to')
        raw_cc = request.data.get('cc', [])
        if not body_text:
            return Response({'detail': 'body_text is required.'}, status=400)
        if not isinstance(raw_to, list):
            return Response({'detail': 'to must be a list of addresses.'}, status=400)
        if not isinstance(raw_cc, list):
            return Response({'detail': 'cc must be a list of addresses.'}, status=400)
        to = [addr.strip() for addr in raw_to if (addr or '').strip()]
        cc = [addr.strip() for addr in raw_cc if (addr or '').strip()]
        if not to:
            return Response({'detail': 'At least one To address is required.'}, status=400)
        invalid = invalid_email_addresses(to + cc)
        if invalid:
            return Response({'detail': f'Not a valid email address: {", ".join(invalid)}'}, status=400)
        reason = mailbox.compose_reply_draft(message, body_text, to, cc, user=request.user)
        if reason:
            return Response({'detail': reason}, status=400)
        message.refresh_from_db()
        return Response(MailboxMessageWithSuggestionsSerializer(message).data)

class MailboxDraftViewSet(viewsets.GenericViewSet):
    """TASK-122 AC1. MailboxDraft is documented append-only (see its model docstring) and, like
    MailboxMessageViewSet above, exposes only one narrow write path -- editing a draft's own text --
    never a generic list/retrieve/PATCH/DELETE. Scoped through the job the draft is attached to
    (accessible_jobs), the same scoping the job itself uses, so a draft on a job this user cannot see
    404s rather than leaking its text.
    """
    serializer_class=MailboxDraftSerializer
    def get_queryset(self):
        return MailboxDraft.objects.filter(job__in=accessible_jobs(self.request.user))
    @action(detail=True, methods=['post'])
    def edit(self, request, pk=None):
        """TASK-122 AC1: the floor this whole feature rests on -- editing a draft's text by hand,
        with no model involved. update_draft_text re-runs check_guardrails on the new text and
        updates Gmail Drafts itself (TASK-121's stored draft id); a guardrail refusal leaves the
        stored draft unchanged and reports why, the same '' = ok / reason-string = blocked
        convention check_guardrails itself already uses.
        """
        draft=self.get_object()
        new_text=(request.data.get('body_text') or '').strip()
        if not new_text:
            return Response({'detail':'body_text is required.'}, status=400)
        reason=mailbox.update_draft_text(draft, new_text, user=request.user)
        if reason:
            return Response({'detail': reason}, status=400)
        # TASK-122 AC4/AC5: whatever conversation led here is spent the moment its result is
        # accepted -- the accepted text is body_text's new baseline going forward, so a later chat
        # turn must re-feed IT as the "original draft", not a transcript that ends at older text
        # update_draft_text just overwrote. mailbox.py is out of this task's file scope, so the
        # reset happens here rather than inside update_draft_text itself.
        MailboxDraft.objects.filter(pk=draft.pk).update(chat_history=[])
        draft.refresh_from_db()
        return Response(self.get_serializer(draft).data)
    @action(detail=False, methods=['get'], url_path='model-options')
    def model_options(self, request):
        """TASK-122 AC3/AC4: the same machine-capability probe CV generation already uses (never a
        second one), plus the owner's last-chosen (provider, model) so the picker does not reset on
        every mount the way CV generation's does.
        """
        profile=user_profile_settings(request.user)
        return Response({
            'models': available_model_options(),
            'selected_provider': profile.mailbox_chat_provider,
            'selected_model': profile.mailbox_chat_model,
        })
    @action(detail=True, methods=['post'])
    def chat(self, request, pk=None):
        """TASK-122 AC2/AC3/AC4/AC6/AC7/AC8: one turn of the draft-revision conversation.
        Rebuilds `history` from chat_history (never trusts the client to resend it -- the stored
        JSON is the one source of truth), calls run_chat_turn, and returns the revision for the
        owner to look at. NEVER writes to Gmail or to `body_text` here (AC5's write-through only
        happens via `edit` above, on explicit accept) -- see draft_chat's module docstring.

        The (provider, model) requested is persisted onto the user's profile immediately (AC4),
        regardless of whether this particular turn succeeds -- it is what the owner picked in the
        UI, and CV generation's picker resetting on every mount is exactly the annoyance this must
        not repeat. Only a turn with reason == '' (AC7: no provider failure, AC6: no guardrail
        block) is appended to chat_history; a refused turn changes nothing on record, so a later
        turn still re-feeds the last text that was actually safe to show.
        """
        draft=self.get_object()
        user_message=(request.data.get('user_message') or '').strip()
        if not user_message:
            return Response({'detail':'user_message is required.'}, status=400)
        provider=request.data.get('provider') or ''
        model=request.data.get('model') or ''
        effort=request.data.get('effort') or ''
        speed=request.data.get('speed') or 'normal'
        profile=user_profile_settings(request.user)
        if provider and model and (profile.mailbox_chat_provider != provider or profile.mailbox_chat_model != model):
            profile.mailbox_chat_provider=provider
            profile.mailbox_chat_model=model
            profile.save(update_fields=['mailbox_chat_provider','mailbox_chat_model'])
        history=[ChatTurn(**item) for item in draft.chat_history]
        result=run_chat_turn(draft.body_text, history, user_message, provider, model, effort, speed, profile=profile)
        if result.reason:
            return Response({'detail': result.reason}, status=400)
        draft.chat_history=draft.chat_history + [{'user_message': user_message, 'revised_text': result.revised_text}]
        draft.save(update_fields=['chat_history'])
        return Response(self.get_serializer(draft).data)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def raise_test_error(request):
    """TASK-88 AC2: deliberately raise, so the alerting path can be proven end to end in production.

    AC1 wired unhandled 500s to AdminEmailHandler, but "it is configured" and "an alert actually
    arrives in the owner's inbox" are different claims, and only the second one is worth anything at
    3am. There was no way to make the app fail on purpose, so the channel had never been exercised
    against production -- ERROR_ALERT_EMAILS, the Brevo relay, SERVER_EMAIL being a verified sender,
    and the cooldown all had to be right simultaneously, untested.

    Owner-gated (is_cv_owner -- unlike /api/mailbox-runs/, which switched to is_mailbox_owner in
    TASK-151, this stays on is_cv_owner: it is not a mailbox endpoint, and CODEX_CV_ENABLED being
    off wherever DEBUG is off is an acceptable reason for the alerting self-test to be unreachable
    too) and POST-only, so it cannot be reached by a stray GET, a crawler, or another account.
    Kept rather than deleted after the first
    successful alert: the same three things can silently rot -- a Brevo key rotates, a sender
    verification lapses, a recipient changes -- and this is how you find out before an outage does
    rather than after.
    """
    if not is_cv_owner(request.user):
        return Response({'detail': 'Not found.'}, status=404)
    raise RuntimeError('TASK-88 AC2: deliberate test error, raised on purpose to prove alerting works.')

@api_view(['POST'])
def practice_evaluate(request):
    """TASK-104: score an interview answer and record the attempt for this user only."""
    ser=PracticeEvaluateSerializer(data=request.data, context={'request': request})
    ser.is_valid(raise_exception=True)
    question=ser.validated_data.get('question') or ''
    answer_text=ser.validated_data['answer_text']
    language=ser.validated_data['language']
    job=ser.validated_data.get('job')
    result=analyze_answer(question, answer_text, language, job=job)
    session=PracticeSession.objects.create(
        user=request.user, job=job, question=question, answer_text=answer_text, language=language,
        clarity_score=result.clarity, structure_score=result.structure, confidence_score=result.confidence, overall_score=result.overall,
        feedback=result.feedback, stronger_answer=result.stronger_answer, evaluator=result.evaluator, model=result.model or '', fallback_used=result.fallback_used,
    )
    return Response(PracticeSessionSerializer(session, context={'request': request}).data, status=201)

@api_view(['GET'])
def practice_history(request):
    """Per-user practice history, newest first (model ordering), optionally scoped to one job."""
    qs=PracticeSession.objects.filter(user=request.user).select_related('job')
    if request.query_params.get('job'):
        qs=qs.filter(job_id=request.query_params['job'])
    return Response(PracticeSessionSerializer(qs, many=True, context={'request': request}).data)

@api_view(['GET'])
def practice_questions(request):
    """TASK-106: suggested practice questions, grounded in a linked job's evaluation when there is one."""
    language=request.query_params.get('language', 'en')
    if language not in dict(PracticeSession.LANGUAGES):
        return Response({'detail': 'Unsupported language.'}, status=400)
    job=None
    job_id=request.query_params.get('job')
    if job_id:
        job=accessible_jobs(request.user).filter(pk=job_id).first()
        if job is None:
            return Response({'detail': 'Job not found.'}, status=404)
    result=suggest_questions(job, language)
    return Response({
        'questions': result.questions, 'grounded': result.grounded, 'notice': result.notice,
        'evaluator': result.evaluator, 'model': result.model, 'fallback_used': result.fallback_used,
    })

@api_view(['POST'])
def bulk_create_jobs(request):
    pasted=(request.data.get('url') or '') + '\n' + (request.data.get('raw_description') or '')
    links=extract_links(pasted)
    if not links:
        if not any((request.data.get(f) or '').strip() for f in ['company','title','raw_description']):
            return Response({'detail':'Paste at least one valid link, or add company/title/description details.'}, status=400)
        links=['']
    conflicts=[]; created=[]; updated=[]; skipped=[]
    strategy=request.data.get('duplicate_action') or request.data.get('duplicate_strategy')
    action_map={a.get('index'):a.get('action') for a in request.data.get('duplicate_actions',[])}
    owned_qs=accessible_jobs(request.user)
    for i, link in enumerate(links):
        existing=find_existing_by_url(link, queryset=owned_qs) if link else None
        action=action_map.get(i) or strategy
        if existing and not action:
            conflicts.append({'index':i,'url':link,'incoming':{'company':request.data.get('company') or 'Unknown company','title':request.data.get('title') or 'Untitled role'},'existing_jobs':[JobLeadSerializer(existing).data]})
    if conflicts and not action_map:
        return Response({'ok':False,'type':'duplicate_conflicts','message':'One or more job links already exist. Nothing was added yet.','conflicts':conflicts}, status=400)
    remaining=[c for c in conflicts if c['index'] not in action_map]
    for i, link in enumerate(links):
        if remaining and action_map and i not in action_map:
            continue
        data=request.data.copy(); data['url']=link; data['company']=data.get('company') or 'Unknown company'; data['title']=data.get('title') or 'Untitled role'
        if len(links)>1 and (not request.data.get('title')): data['title']=f'Untitled role {i+1}'
        existing=find_existing_by_url(link, queryset=owned_qs) if link else None
        action=action_map.get(i) or strategy
        if existing and action=='skip':
            skipped.append({'index':i,'url':link}); continue
        if existing and action=='override':
            replace_job_with_supplied_data(existing, data, request.user)
            updated.append(JobLeadSerializer(existing).data); continue
        if existing and action=='duplicate': data['title']=duplicate_title(data.get('title') or 'Untitled role', owned_qs)
        ser=JobLeadSerializer(data=data, context={'request': request}); ser.is_valid(raise_exception=True); obj=ser.save(**job_create_defaults(request.user)); created.append(JobLeadSerializer(obj).data)
    if remaining:
        return Response({'ok':False,'type':'duplicate_conflicts','message':'One or more job links still need a duplicate choice.','conflicts':remaining,'created':created,'updated':updated,'skipped':skipped}, status=400)
    return Response({'ok':True,'count':len(created)+len(updated),'created':created,'updated':updated,'skipped':skipped}, status=201)

@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([PublicSubmitIPThrottle])
def public_submit(request):
    if not request.user.is_authenticated:
        code=(request.data.get('invite_code') or '').strip()
        invite=InviteCode.objects.filter(code=code).first()
        if not invite or not invite.is_valid(): return Response({'detail':'Invalid invite code'}, status=400)
    profile=getattr(request.user, 'jobradar_profile', None)
    # A friend named at registration is only resolved once the address is confirmed (TASK-93), so
    # both halves of "named a friend, not approved yet" have to block. Without the first check the
    # submission would quietly land on the submitter's own board instead of the friend's.
    if profile and not profile.submit_for_id and profile.pending_friend_lookup:
        return Response({'detail':'Confirm your email address first -- your friend is asked to approve you once you do.'}, status=403)
    if profile and profile.requested_submit_for_id and not profile.submit_for_id:
        return Response({'detail':'Your friend has not approved this submission link yet.'}, status=403)
    owner=profile.submit_for if profile and profile.submit_for_id else (request.user if request.user.is_authenticated else None)
    links=extract_links((request.data.get('url') or '') + '\n' + (request.data.get('raw_description') or '')) or ['']
    strategy=request.data.get('duplicate_strategy') or request.data.get('duplicate_action')
    action_map={a.get('index'):a.get('action') for a in request.data.get('duplicate_actions',[])}
    conflicts=[]; created=[]; skipped=[]
    # The duplicate check runs against the *recipient's* board, so the matched row is the
    # recipient's job, not the submitter's. Anyone but the recipient gets the submission-only
    # projection of it -- otherwise this endpoint hands a friend (or, with invite codes, an
    # anonymous submitter) the recipient's evaluation for the price of guessing a job URL.
    def conflict_job(existing):
        data=JobLeadSerializer(existing).data
        return data if owner is not None and owner == request.user else submission_row(data)
    for i, link in enumerate(links):
        existing=find_existing_by_url(link, owner)
        action=action_map.get(i) or strategy
        if existing and not action:
            conflicts.append({'index':i,'url':link,'incoming':{'company':request.data.get('company') or 'Unknown company','title':request.data.get('title') or 'Untitled role'},'existing_jobs':[conflict_job(existing)]})
    if conflicts and not action_map:
        return Response({'ok':False,'type':'duplicate_conflicts','message':'Some links already exist in this dashboard. Choose which ones to duplicate or skip.','conflicts':conflicts}, status=400)
    remaining=[c for c in conflicts if c['index'] not in action_map]
    for i, link in enumerate(links):
        existing=find_existing_by_url(link, owner) if link else None
        action=action_map.get(i) or strategy
        if remaining and action_map and i not in action_map: continue
        if existing and action!='duplicate': skipped.append({'index':i,'url':link}); continue
        data=request.data.copy(); data['url']=link; data['company']=data.get('company') or 'Unknown company'; data['title']=data.get('title') or ('Untitled role' if len(links)==1 else f'Untitled role {i+1}')
        if existing and action=='duplicate': data['title']=duplicate_title(data.get('title') or 'Untitled role', JobLead.objects.filter(Q(created_by=owner)|Q(submitted_for=owner)) if owner else None)
        ser=PublicSubmissionSerializer(data=data); ser.is_valid(raise_exception=True)
        job=ser.save()
        if request.user.is_authenticated:
            job.created_by=request.user; job.submitted_for=profile.submit_for if profile else None; job.save(update_fields=['created_by','submitted_for'])
        created.append(JobLeadSerializer(job).data)
    if remaining:
        return Response({'ok':False,'type':'duplicate_conflicts','message':'Some links already exist in this dashboard. Choose which ones to duplicate or skip.','conflicts':remaining,'created':created,'skipped':skipped}, status=400)
    return Response({'ok':True,'count':len(created),'created':created,'skipped':skipped}, status=201)

@api_view(['POST'])
def generate_prompt(request):
    ids=request.data.get('job_ids') or []
    jobs=accessible_jobs(request.user).filter(id__in=ids)
    if not ids or jobs.count()!=len(set(ids)): return Response({'detail':'Provide valid job_ids'}, status=400)
    profile=user_profile_settings(request.user)
    return Response({'generated_prompt': build_prompt(jobs, request.data.get('custom_instructions',''), build_candidate_profile_text(request.user), profile.evaluation_prompt_template)})

@api_view(['POST'])
def generate_combined_prompt(request):
    ids=request.data.get('job_ids') or []
    jobs=accessible_jobs(request.user).filter(id__in=ids)
    if not ids or jobs.count()!=len(set(ids)): return Response({'detail':'Provide valid job_ids'}, status=400)
    profile=user_profile_settings(request.user)
    return Response({'generated_prompt': build_combined_prompt(jobs, request.data.get('custom_instructions',''), build_candidate_profile_text(request.user), profile.combined_prompt_template)})

@api_view(['POST'])
def generate_bulk_links_prompt(request):
    raw=request.data.get('links') or request.data.get('text') or ''
    links=[x.strip() for x in raw.replace(',', '\n').splitlines() if x.strip()]
    if not links: return Response({'detail':'Provide one or more links'}, status=400)
    profile=user_profile_settings(request.user)
    return Response({'generated_prompt': build_bulk_links_prompt(links, request.data.get('custom_instructions',''), build_candidate_profile_text(request.user), profile.bulk_links_prompt_template)})

@api_view(['POST'])
def generate_enrichment_prompt(request):
    ids=request.data.get('job_ids') or []
    owned_qs=accessible_jobs(request.user)
    if ids:
        jobs=owned_qs.filter(id__in=ids)
        if jobs.count()!=len(set(ids)): return Response({'detail':'Provide valid job_ids'}, status=400)
    else:
        jobs=owned_qs.filter(Q(company__in=['','Unknown company'])|Q(title__in=['','Untitled role'])|Q(raw_description=''))[:25]
    if not jobs: return Response({'detail':'No jobs need detail enrichment'}, status=400)
    profile=user_profile_settings(request.user)
    return Response({'generated_prompt': build_enrichment_prompt(jobs, request.data.get('custom_instructions',''), build_candidate_profile_text(request.user), profile.enrichment_prompt_template)})

@api_view(['GET'])
def cv_generation_preview(request, job_id):
    if not is_cv_owner(request.user):
        return Response({'detail':'Not found.'}, status=404)
    job=accessible_jobs(request.user).filter(id=job_id).first()
    if not job:
        return Response({'detail':'Job not found.'}, status=404)
    return Response(generation_preview(job, request.user))


def _started_cv_task(task_id, user_id):
    return {'task_id':task_id, **(get_cv_task(task_id,user_id) or {'status':'queued','progress':0,'stage':'Queued','elapsed_seconds':0,'estimated_seconds_remaining':180,'step_label':'Queued','step_completed':0,'step_total':0})}


@api_view(['POST'])
@throttle_classes([CVGenerationUserThrottle])
def generate_cv_documents(request, job_id):
    if not is_cv_owner(request.user):
        return Response({'detail':'Not found.'}, status=404)
    job=accessible_jobs(request.user).filter(id=job_id).first()
    if not job:
        return Response({'detail':'Job not found.'}, status=404)
    create_cv=request.data.get('create_cv', True) is not False
    create_letter=request.data.get('create_letter', True) is not False
    if not create_cv and not create_letter:
        return Response({'detail':'Select at least a CV or a letter.'}, status=400)
    try:
        validate_model_capability(request.data.get('provider') or '', request.data.get('model') or '', request.data.get('effort') or '', request.data.get('speed') or 'normal')
    except ValueError as exc:
        return Response({'detail':str(exc)}, status=400)
    cv_profile=user_profile_settings(request.user)
    try:
        candidate_context=load_candidate_evidence(build_candidate_profile_text(request.user), cv_profile.learned_application_preferences, cv_profile.candidate_evidence)
    except RuntimeError as exc:
        return Response({'detail':str(exc)}, status=503)
    try:
        task_id=start_cv_task(job.id, request.user.id, candidate_context, request.data.get('cv_template') or '', request.data.get('letter_template') or '', create_letter, request.data.get('provider') or '', request.data.get('model') or '', request.data.get('effort') or '', request.data.get('speed') or 'normal', create_cv=create_cv)
    except RuntimeError:
        return Response({'detail':'CV generation is restarting. Try again shortly.'}, status=503)
    return Response(_started_cv_task(task_id,request.user.id), status=status.HTTP_202_ACCEPTED)


@api_view(['POST'])
@throttle_classes([CVGenerationUserThrottle])
def recompile_latest_cv_documents(request, job_id):
    if not is_cv_owner(request.user):
        return Response({'detail':'Not found.'},status=404)
    job=accessible_jobs(request.user).filter(id=job_id).first()
    if not job:
        return Response({'detail':'Job not found.'},status=404)
    cv_key=request.data.get('cv_template') or ''
    source_cv,source_letter=latest_generated_sources(job,request.user)
    source_cv=source_cv if request.data.get('create_cv',True) is not False else None
    source_letter=source_letter if request.data.get('create_letter',True) is not False else None
    if not source_cv and not source_letter:
        return Response({'detail':'No previous generated TeX files were found for this job.'},status=400)
    task_id=start_cv_compile_task(job.id,request.user.id,cv_key,source_cv,source_letter)
    return Response(_started_cv_task(task_id,request.user.id),status=status.HTTP_202_ACCEPTED)


@api_view(['POST'])
@throttle_classes([CVGenerationUserThrottle])
def revise_latest_cv_documents(request, job_id):
    if not is_cv_owner(request.user):
        return Response({'detail':'Not found.'}, status=404)
    job=accessible_jobs(request.user).filter(id=job_id).first()
    if not job:
        return Response({'detail':'Job not found.'}, status=404)
    instructions=(request.data.get('instructions') or '').strip()
    try:
        correction_image=decode_correction_image(request.data.get('correction_image'))
    except ValueError as exc:
        return Response({'detail':str(exc)}, status=400)
    create_cv=request.data.get('create_cv', True) is not False
    create_letter=request.data.get('create_letter', True) is not False
    if not (instructions or correction_image) or not (create_cv or create_letter):
        return Response({'detail':'Provide revision instructions or a correction image and select at least one document.'}, status=400)
    cv_key=request.data.get('cv_template') or ''
    source_cv,source_letter=latest_generated_sources(job, request.user)
    create_cv=create_cv and bool(source_cv)
    create_letter=create_letter and bool(source_letter)
    if not create_cv and not create_letter:
        return Response({'detail':'No previous generated files were found for this job.'}, status=400)
    try:
        validate_model_capability(request.data.get('provider') or '', request.data.get('model') or '', request.data.get('effort') or '', request.data.get('speed') or 'normal')
    except ValueError as exc:
        return Response({'detail':str(exc)}, status=400)
    cv_profile=user_profile_settings(request.user)
    try:
        candidate_context=load_candidate_evidence(build_candidate_profile_text(request.user), cv_profile.learned_application_preferences, cv_profile.candidate_evidence)
    except RuntimeError as exc:
        return Response({'detail':str(exc)}, status=503)
    try:
        task_id=start_cv_task(job.id, request.user.id, candidate_context, cv_key, request.data.get('letter_template') or '', create_letter, request.data.get('provider') or '', request.data.get('model') or '', request.data.get('effort') or '', request.data.get('speed') or 'normal', source_cv=source_cv, source_letter=source_letter, revision_instructions=instructions[:5000], create_cv=create_cv, correction_image=correction_image)
    except RuntimeError:
        return Response({'detail':'CV generation is restarting. Try again shortly.'}, status=503)
    return Response(_started_cv_task(task_id,request.user.id), status=status.HTTP_202_ACCEPTED)


@api_view(['GET'])
def cv_generation_status(request, task_id):
    if not is_cv_owner(request.user):
        return Response({'detail':'Not found.'}, status=404)
    task=get_cv_task(task_id, request.user.id)
    return Response(task) if task else Response({'detail':'Task not found.'}, status=404)


@api_view(['GET'])
def mailbox_check_task_status(request, task_id):
    """TASK-124 AC1: polling for the specific in-thread task run-now just started -- same
    shape/gate as cv_generation_status above. Only reachable when the run started on THIS
    process's thread (see services.mailbox_tasks); a queued request (no credentials) has no task
    to poll here at all -- the caller should watch /api/mailbox-runs/status/ instead."""
    if not is_cv_owner(request.user):
        return Response({'detail':'Not found.'}, status=404)
    task=mailbox_tasks.get_mailbox_check_task(task_id, request.user.id)
    return Response(task) if task else Response({'detail':'Task not found.'}, status=404)


@api_view(['POST'])
def reveal_cv_artifact(request, task_id):
    if not is_cv_owner(request.user):
        return Response({'detail':'Not found.'}, status=404)
    key=request.data.get('key','')
    if key not in ARTIFACT_KEYS:
        return Response({'detail':f'Unknown artifact. Expected one of: {", ".join(ARTIFACT_KEYS)}.'}, status=400)
    task=get_cv_task(task_id, request.user.id)
    if not task:
        return Response({'detail':'Task not found.'}, status=404)
    # The path comes from the task's own artifacts, keyed by the whitelisted key -- never from the body.
    path=(task.get('artifacts') or {}).get(key)
    if not path:
        return Response({'detail':'That artifact was not generated for this task.'}, status=404)
    if not reveal_artifact_folder(path):
        return Response({'detail':'Opening folders is disabled on this server.'}, status=409)
    return Response({'revealed':path})


@api_view(['POST'])
def cancel_cv_generation(request, task_id):
    if not is_cv_owner(request.user):
        return Response({'detail':'Not found.'}, status=404)
    result=cancel_cv_task(task_id, request.user.id)
    if result is None:
        return Response({'detail':'Task not found.'}, status=404)
    if result is False:
        return Response({'detail':'Task already finished.'}, status=409)
    return Response(get_cv_task(task_id,request.user.id), status=status.HTTP_202_ACCEPTED)


@api_view(['POST'])
@throttle_classes([CVGenerationUserThrottle])
def revise_cv_documents(request, task_id):
    if not is_cv_owner(request.user):
        return Response({'detail':'Not found.'}, status=404)
    try:
        correction_image=decode_correction_image(request.data.get('correction_image'))
        new_task_id=start_cv_revision(task_id, request.user.id, request.data.get('instructions') or '', correction_image)
    except ValueError as exc:
        return Response({'detail':str(exc)}, status=400)
    except RuntimeError:
        return Response({'detail':'CV generation is restarting. Try again shortly.'}, status=503)
    return Response(_started_cv_task(new_task_id,request.user.id), status=status.HTTP_202_ACCEPTED)


@api_view(['GET'])
def cv_generation_download(request, task_id):
    if not is_cv_owner(request.user):
        return Response({'detail':'Not found.'}, status=404)
    result=get_cv_task_download(task_id, request.user.id)
    if not result:
        return Response({'detail':'File is not ready.'}, status=404)
    archive, filename=result
    response=HttpResponse(archive, content_type='application/zip')
    response['Content-Disposition']=f'attachment; filename="{filename}"'
    return response


@api_view(['POST'])
@throttle_classes([ImportUserThrottle])
def import_eval(request):
    result=import_any_json(request.data.get('json') or request.data.get('pasted_json') or request.data, user=request.user)
    return Response(result, status=201 if result.get('ok') else 400)

@api_view(['GET'])
def stats(request):
    jobs=accessible_jobs(request.user)
    today=timezone.localdate(); evaluations=JobEvaluation.objects.filter(job__in=jobs)
    applied_jobs=jobs.filter(applied_at__isnull=False)
    week_start=today-timezone.timedelta(days=today.weekday())
    month_start=today.replace(day=1)
    next_month=(today.replace(year=today.year+1, month=1, day=1) if today.month == 12 else today.replace(month=today.month+1, day=1))
    month_end=next_month-timezone.timedelta(days=1)
    weekly_applications=[]
    for i in range(3,-1,-1):
        start=week_start-timezone.timedelta(days=i*7)
        end=start+timezone.timedelta(days=6)
        weekly_applications.append({'label':start.strftime('%d %b'), 'start':start.isoformat(), 'end':end.isoformat(), 'count':applied_jobs.filter(applied_at__gte=start, applied_at__lte=end).count()})
    month_week_applications=[]
    suffixes=['st','nd','rd']
    cursor=month_start
    idx=1
    while cursor <= month_end:
        end=min(cursor+timezone.timedelta(days=6), month_end)
        suffix=suffixes[idx-1] if idx <= 3 else 'th'
        month_week_applications.append({'label':f'{idx}{suffix} week', 'range':f'{cursor.day}-{end.day} {end.strftime("%b")}', 'start':cursor.isoformat(), 'end':end.isoformat(), 'count':applied_jobs.filter(applied_at__gte=cursor, applied_at__lte=end).count()})
        cursor=end+timezone.timedelta(days=1)
        idx+=1
    workday_applications=[]
    cursor=month_start
    while cursor <= month_end:
        if cursor.weekday() < 5:
            workday_applications.append({'label':cursor.strftime('%d %b'), 'date':cursor.isoformat(), 'count':applied_jobs.filter(applied_at=cursor).count()})
        cursor+=timezone.timedelta(days=1)
    applications_this_week=applied_jobs.filter(applied_at__gte=week_start, applied_at__lte=today).count()
    elapsed_workdays=sum(1 for i in range(min(today.weekday(), 4)+1))
    # Only interviews still ahead of us, soonest first; a date that has passed drops out on its own.
    upcoming_interviews=[{'id':j.id, 'company':j.company, 'title':j.title, 'interview_at':j.interview_at, 'interview_note':j.interview_note}
                         for j in jobs.filter(interview_at__gte=timezone.now()).exclude(status__in=['rejected','withdrawn','skipped','archived']).order_by('interview_at')[:10]]
    recent_start=today-timezone.timedelta(days=JobLead.FUNNEL_RECENT_DAYS)
    funnel={'recent_window_days':JobLead.FUNNEL_RECENT_DAYS, 'recent_window_start':recent_start.isoformat(),
            'all_time':funnel_counts(applied_jobs),
            'recent':funnel_counts(applied_jobs.filter(applied_at__gte=recent_start)),
            # Jobs sitting in interview/offer that were never marked applied. Excluded from every
            # rate above so none can exceed 100%, surfaced here so the gap is visible and fixable.
            'interviews_without_application':jobs.filter(REACHED_INTERVIEW, applied_at__isnull=True).count()}
    return Response({'total_jobs':jobs.count(), 'funnel':funnel, 'source_effectiveness':source_effectiveness(applied_jobs), 'jobs_by_status':dict(jobs.values_list('status').annotate(c=Count('id'))), 'average_fit_score':evaluations.aggregate(a=Avg('fit_score'))['a'] or 0, 'high_priority_jobs':evaluations.filter(priority='high', job__status='new').values('job').distinct().count(), 'applications_sent':applied_jobs.count(), 'applications_this_week':applications_this_week, 'applications_per_workday':round(applications_this_week/max(elapsed_workdays,1), 1), 'workday_applications':workday_applications, 'month_week_applications':month_week_applications, 'weekly_applications':weekly_applications, 'interviews':jobs.filter(status='interview').count(), 'upcoming_interviews':upcoming_interviews, 'offers':jobs.filter(status='offer').count(), 'accepted':jobs.filter(status='accepted').count(), 'rejected':jobs.filter(status='rejected').count(), 'withdrawn':jobs.filter(status='withdrawn').count(), 'jobs_needing_follow_up':FollowUp.objects.filter(job__in=jobs, completed=False, follow_up_date__lte=today).count()})

@api_view(['GET', 'POST'])
def export_user_data(request):
    fmt=(request.query_params.get('type') or request.data.get('type') or 'json').lower()
    kind=(request.query_params.get('kind') or request.data.get('kind') or 'jobs').lower()
    preferences=request.data.get('preferences') if hasattr(request, 'data') and isinstance(request.data, dict) else None
    if fmt == 'csv':
        response=HttpResponse(export_user_data_csv(request.user, preferences, kind), content_type='text/csv')
        response['Content-Disposition']=f'attachment; filename="dachapply-{kind}.csv"'
        return response
    if fmt == 'xlsx':
        response=HttpResponse(export_user_data_xlsx(request.user, preferences, kind), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition']=f'attachment; filename="dachapply-{kind}.xlsx"'
        return response
    if kind == 'preferences':
        payload={'schema_version': SCHEMA_VERSION, 'app': APP_NAME, 'exported_at': timezone.now().isoformat(), 'type': 'preferences', 'frontend_preferences': preferences or {}}
    else:
        payload=build_user_export(request.user)
        if kind == 'full':
            payload['frontend_preferences']=preferences or {}
    response = Response(payload)
    response['Content-Disposition'] = f'attachment; filename="dachapply-{kind}.json"'
    return response

@api_view(['POST'])
@throttle_classes([ImportUserThrottle])
def import_user_data(request):
    try:
        payload = parse_import_payload(request)
    except ValueError as exc:
        return Response({'created': {}, 'updated': {}, 'skipped': {}, 'errors': [str(exc)]}, status=400)
    summary = import_user_export(request.user, payload)
    return Response(summary, status=400 if summary.get('errors') or summary.get('type') == 'import_conflicts' else 200)

@api_view(['GET'])
def export_jobs_json(request): return HttpResponse(jobs_json(accessible_jobs(request.user)), content_type='application/json')
@api_view(['GET'])
def export_jobs_csv(request):
    r=HttpResponse(jobs_csv(accessible_jobs(request.user)), content_type='text/csv'); r['Content-Disposition']='attachment; filename="jobs.csv"'; return r
@api_view(['GET'])
def export_chatgpt_brief(request): return HttpResponse(chatgpt_brief(accessible_jobs(request.user), build_candidate_profile_text(request.user)), content_type='text/markdown')
