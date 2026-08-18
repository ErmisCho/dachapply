import logging
from html import escape

from django.contrib.auth import authenticate, login, logout, get_user_model
from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import send_mail
from django.db import connection, transaction
from django.db.models import Avg, Case, Count, F, IntegerField, Q, Value, When
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
from .models import JobLead, JobEvaluation, ApplicationNote, FollowUp, MailboxMessage, MailboxRun, MailboxSuggestion, PracticeSession, UserProfile, InviteCode
from .serializers import CandidateProfileSerializer, JobLeadSerializer, JobLeadListSerializer, JobEvaluationSerializer, ApplicationNoteSerializer, FollowUpSerializer, MailboxMessageSerializer, MailboxMessageWithSuggestionsSerializer, MailboxRunSerializer, MailboxSuggestionSerializer, PracticeEvaluateSerializer, PracticeSessionSerializer, PublicSubmissionSerializer, normalize_job_url
from .services.prompt_builder import build_prompt, build_enrichment_prompt, build_bulk_links_prompt, build_combined_prompt, build_candidate_profile_text, has_candidate_profile, user_profile_settings
from .services.json_importer import import_any_json, duplicate_title
from .services.exporters import jobs_json, jobs_csv, chatgpt_brief
from .services.user_data_portability import APP_NAME, SCHEMA_VERSION, build_user_export, export_user_data_csv, export_user_data_xlsx, import_user_export, parse_import_payload
from .services.access import accessible_jobs, job_create_defaults, owned_by, submitted_away_jobs
from .services.cleaning import clean_job_location
from .services.job_replace import replace_job_with_supplied_data
from .services.demo_data import DEMO_PASSWORD, DEMO_USERNAME, ensure_demo_user
from .services.interview_coach import analyze_answer, suggest_questions
from .services.mailbox import apply_suggestion, attach_message_to_job, dismiss_suggestion
from .services.analytics import record_demo_click
from .services.cv_generator import ARTIFACT_KEYS, decode_correction_image, generation_preview, is_cv_owner, latest_generated_sources, load_candidate_evidence, reveal_artifact_folder, validate_model_capability
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
}


# The board's default ordering: urgency first, then the server-side formula. Sorting is an
# opt-in override of this, never a replacement -- ?ordering= absent, empty or unrecognised
# lands here.
DEFAULT_BOARD_ORDERING = ('stale_rank', 'status_rank', 'priority_rank', '-evaluations__fit_score', '-created_at')

# TASK-97/TASK-108's sort control. The query parameter is a lookup *key*, never an argument to
# order_by(): passing it through would let a client order by any related column
# (?ordering=-created_by__password) and read values off the resulting row order, which is
# information disclosure, not just untidy. An unknown key simply misses the dict.
# 'status' points at status_pipeline_rank (built below from JobLead.STATUSES), not status_rank
# -- status_rank is an attention order DEFAULT_BOARD_ORDERING depends on, and collapses
# interview/offer together, which is wrong for a user explicitly sorting by pipeline stage.
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
        qs=qs.annotate(
            # -1 surfaces, 1 sinks. One expression owns every age/deadline signal on the board.
            stale_rank=Case(
                When(status__in=JobLead.UNAPPLIED_STATUSES, apply_by__lte=today+timezone.timedelta(days=JobLead.DEADLINE_SOON_DAYS), then=Value(-1)),
                When(status__in=JobLead.DATED_STATUSES, status_date__lt=today-timezone.timedelta(days=JobLead.STALE_APPLIED_DAYS), then=Value(1)),
                When(status__in=JobLead.UNAPPLIED_STATUSES, created_at__lt=timezone.now()-timezone.timedelta(days=JobLead.STALE_UNAPPLIED_DAYS), then=Value(1)),
                default=Value(0), output_field=IntegerField()),
            status_rank=Case(When(status='new', then=Value(0)), When(status='to_apply', then=Value(1)), When(status='reviewed', then=Value(2)), When(status__in=['interview','offer'], then=Value(3)), When(status='applied', then=Value(4)), default=Value(5), output_field=IntegerField()),
            priority_rank=Case(When(evaluations__priority='high', then=Value(0)), When(evaluations__priority='medium', then=Value(1)), When(evaluations__priority='low', then=Value(2)), default=Value(3), output_field=IntegerField()),
            # TASK-108: pipeline order for ordering=status, distinct from status_rank's attention
            # order above -- see BOARD_ORDERINGS' comment.
            status_pipeline_rank=_status_pipeline_rank(),
        ).order_by(*parse_board_ordering(p.get('ordering')))
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
        """TASK-117 AC2: this job's mailbox messages, newest first, each with its draft and pending
        suggestions. self.get_object() runs against get_queryset() (accessible_jobs) exactly like
        every other detail action above -- a job this user cannot see 404s before any message is read.
        """
        job=self.get_object()
        messages=job.mailbox_messages.select_related('matched_job').prefetch_related('draft','suggestions').order_by('-uid')
        return Response(MailboxMessageWithSuggestionsSerializer(messages, many=True).data)

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

class MailboxRunViewSet(viewsets.ReadOnlyModelViewSet):
    """TASK-109 AC4. Runs are not per-job, so accessible_jobs scoping does not apply -- gated on
    is_cv_owner instead, the same single-owner gate CV generation uses, since this is inherently a
    personal-mailbox audit trail rather than shared board data.
    """
    serializer_class=MailboxRunSerializer
    def get_queryset(self):
        if not is_cv_owner(self.request.user): return MailboxRun.objects.none()
        return MailboxRun.objects.all().prefetch_related('messages__matched_job','messages__draft')

class MailboxMessageViewSet(viewsets.GenericViewSet):
    """TASK-117 AC6/AC7. MailboxMessage.uid is globally unique with no user FK -- the mailbox
    subsystem is single-owner by construction, so this is gated on is_cv_owner exactly like
    MailboxRunViewSet above, not on accessible_jobs. Exposes only what AC6 needs (the unmatched list
    and the manual attach action) -- never a generic list/retrieve/PATCH/DELETE, keeping the model's
    append-only guarantee true for everything except the one owner-initiated attach.
    """
    serializer_class=MailboxMessageSerializer
    def get_queryset(self):
        if not is_cv_owner(self.request.user): return MailboxMessage.objects.none()
        return MailboxMessage.objects.all()
    @action(detail=False, methods=['get'])
    def unmatched(self, request):
        qs=self.get_queryset().exclude(classification='not_job_related').filter(matched_job__isnull=True).order_by('-uid')
        return Response(MailboxMessageSerializer(qs, many=True).data)
    @action(detail=True, methods=['post'])
    def attach(self, request, pk=None):
        """TASK-117 AC6: the only writer of `matched_job` for a message that already ran through
        check_mailbox -- everything else about MailboxMessage stays append-only. self.get_object()
        already applies the is_cv_owner gate via get_queryset(); the target job additionally has to
        be one this user can already see (accessible_jobs), or it 404s the same way reading that job
        would. Re-attaching to the SAME job is a no-op (attach_message_to_job is idempotent);
        attaching to a DIFFERENT job than the one already matched is refused rather than silently
        re-pointing the message.
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
