import logging
from html import escape

from django.contrib.auth import authenticate, login, logout, get_user_model
from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.db import connection, transaction
from django.db.models import Avg, Case, Count, IntegerField, Q, Value, When
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
from .models import JobLead, JobEvaluation, ApplicationNote, FollowUp, UserProfile, InviteCode
from .serializers import CandidateProfileSerializer, JobLeadSerializer, JobEvaluationSerializer, ApplicationNoteSerializer, FollowUpSerializer, PublicSubmissionSerializer, normalize_job_url
from .services.prompt_builder import build_prompt, build_enrichment_prompt, build_bulk_links_prompt, build_combined_prompt, build_candidate_profile_text, user_profile_settings
from .services.json_importer import import_any_json, duplicate_title
from .services.exporters import jobs_json, jobs_csv, chatgpt_brief
from .services.user_data_portability import APP_NAME, SCHEMA_VERSION, build_user_export, export_user_data_csv, export_user_data_xlsx, import_user_export, parse_import_payload
from .services.access import accessible_jobs, job_create_defaults
from .services.cleaning import clean_job_location
from .services.demo_data import DEMO_PASSWORD, DEMO_USERNAME, ensure_demo_user
from .services.analytics import record_demo_click
from .throttles import ImportUserThrottle, LoginAccountThrottle, LoginIPThrottle, PasswordResetEmailThrottle, PasswordResetIPThrottle, PublicSubmitIPThrottle, RegisterIPThrottle


logger = logging.getLogger(__name__)


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
    login(request, user); return Response({'username':user.username})

@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([RegisterIPThrottle])
def register_view(request):
    email=(request.data.get('email') or request.data.get('username') or '').strip().lower()
    username=email
    password=request.data.get('password') or ''
    if len(password)<6: return Response({'detail':'Password must be at least 6 characters'}, status=400)
    if not email or '@' not in email: return Response({'detail':'Valid email is required'}, status=400)
    User=get_user_model()
    submit_for_lookup=(request.data.get('submit_for_username') or request.data.get('submit_for') or '').strip()
    submit_for=None
    if submit_for_lookup:
        submit_for=User.objects.filter(Q(username__iexact=submit_for_lookup)|Q(email__iexact=submit_for_lookup)).first()
        if not submit_for: return Response({'detail':'Friend username or email not found'}, status=400)
    if User.objects.filter(Q(username__iexact=email)|Q(email__iexact=email)).exists(): return Response({'detail':'Email already exists'}, status=400)
    user=User.objects.create_user(username=username, email=email, password=password)
    UserProfile.objects.create(user=user, requested_submit_for=submit_for)
    login(request, user)
    return Response({'username':user.username, 'submit_for_username':None, 'requested_submit_for_username':submit_for.username if submit_for else None, 'is_friend_submitter':False}, status=201)

@api_view(['POST'])
def logout_view(request): logout(request); return Response({'detail':'logged out'})

@api_view(['POST'])
def change_password(request):
    user=request.user
    current=request.data.get('current_password') or ''
    new=request.data.get('new_password') or request.data.get('password') or ''
    if user.has_usable_password() and not user.check_password(current):
        return Response({'detail':'Current password is incorrect.'}, status=400)
    if len(new)<6:
        return Response({'detail':'New password must be at least 6 characters'}, status=400)
    user.set_password(new); user.save(update_fields=['password'])
    login(request, user)
    return Response({'detail':'Password updated.'})

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
def password_reset_confirm(request):
    try:
        uid=force_str(urlsafe_base64_decode(request.data.get('uid') or ''))
        user=get_user_model().objects.get(pk=uid)
    except Exception:
        return Response({'detail':'Invalid reset link'}, status=400)
    token=request.data.get('token') or ''; password=request.data.get('password') or ''
    if not default_token_generator.check_token(user, token): return Response({'detail':'Invalid or expired reset link'}, status=400)
    if len(password)<6: return Response({'detail':'Password must be at least 6 characters'}, status=400)
    user.set_password(password); user.save(update_fields=['password'])
    return Response({'detail':'Password reset successful'})

@api_view(['DELETE'])
def delete_account(request):
    user=request.user
    password=request.data.get('password') or request.data.get('current_password') or ''
    if user.has_usable_password() and not user.check_password(password):
        return Response({'detail':'Current password is required to delete your account.'}, status=400)
    with transaction.atomic():
        owned_jobs=JobLead.objects.filter(Q(created_by=user)|Q(submitted_for=user)).distinct()
        counts={
            'jobs': owned_jobs.count(),
            'evaluations': JobEvaluation.objects.filter(job__in=owned_jobs).count(),
            'notes': ApplicationNote.objects.filter(Q(job__in=owned_jobs)|Q(created_by=user)).distinct().count(),
            'followups': FollowUp.objects.filter(job__in=owned_jobs).count(),
            'profile': 1 if hasattr(user, 'jobradar_profile') else 0,
        }
        owned_jobs.delete()
        ApplicationNote.objects.filter(created_by=user).update(created_by=None)
        logout(request)
        user.delete()
    return Response({'detail':'Account deleted.', 'deleted': counts})

@api_view(['GET'])
def me(request):
    profile=getattr(request.user, 'jobradar_profile', None)
    submit_for=profile.submit_for if profile else None
    requested=profile.requested_submit_for if profile else None
    return Response({'username':request.user.username, 'is_staff':request.user.is_staff, 'submit_for_username':submit_for.username if submit_for else None, 'requested_submit_for_username':requested.username if requested else None, 'is_friend_submitter':bool(submit_for)})

@api_view(['GET','POST'])
def friend_requests(request):
    if request.method=='GET':
        profiles=UserProfile.objects.filter(requested_submit_for=request.user, submit_for__isnull=True).select_related('user')
        return Response([{'username':p.user.username} for p in profiles])
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
    def get_queryset(self):
        qs=accessible_jobs(self.request.user).prefetch_related('evaluations'); p=self.request.query_params
        if p.get('status'):
            statuses=[s for s in p.get('status','').split(',') if s]
            qs=qs.filter(status__in=statuses)
        else:
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
            s=p['skill']; qs=qs.filter(Q(evaluations__matched_skills__icontains=s)|Q(evaluations__required_skills__icontains=s)|Q(raw_description__icontains=s))
        if p.get('search'):
            s=p['search']; qs=qs.filter(Q(company__icontains=s)|Q(title__icontains=s)|Q(raw_description__icontains=s)|Q(url__icontains=s))
        qs=qs.annotate(
            stale_rank=Case(When(status__in=['applied','interview'], status_date__lt=timezone.localdate()-timezone.timedelta(days=21), then=Value(1)), default=Value(0), output_field=IntegerField()),
            status_rank=Case(When(status='new', then=Value(0)), When(status='to_apply', then=Value(1)), When(status='reviewed', then=Value(2)), When(status='interview', then=Value(3)), When(status='applied', then=Value(4)), default=Value(5), output_field=IntegerField()),
            priority_rank=Case(When(evaluations__priority='high', then=Value(0)), When(evaluations__priority='medium', then=Value(1)), When(evaluations__priority='low', then=Value(2)), default=Value(3), output_field=IntegerField())
        ).order_by('stale_rank','status_rank','priority_rank','-evaluations__fit_score','-created_at')
        return qs.distinct()
    def create(self, request, *args, **kwargs):
        ser=self.get_serializer(data=request.data); ser.is_valid(raise_exception=True)
        url=ser.validated_data.get('url')
        action=request.data.get('duplicate_action')
        existing=find_existing_by_url(url, queryset=accessible_jobs(request.user))
        if existing and not action:
            return Response({'ok':False,'type':'duplicate_conflicts','message':'This job link already exists.','conflicts':[{'index':0,'url':url,'incoming':{'company':ser.validated_data.get('company') or 'Unknown company','title':ser.validated_data.get('title') or 'Untitled role'},'existing_jobs':[JobLeadSerializer(existing).data]}]}, status=400)
        if existing and action=='override':
            for k,v in ser.validated_data.items(): setattr(existing,k,v)
            for k,v in job_create_defaults(request.user).items(): setattr(existing,k,v)
            existing.save(); return Response(JobLeadSerializer(existing).data)
        if existing and action=='duplicate':
            ser.validated_data['title']=duplicate_title(ser.validated_data.get('title') or 'Untitled role', accessible_jobs(request.user))
        if existing and action=='skip': return Response(JobLeadSerializer(existing).data)
        obj=ser.save(**job_create_defaults(request.user)); return Response(JobLeadSerializer(obj).data, status=201)
    def perform_create(self, serializer): serializer.save(**job_create_defaults(self.request.user))
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

class EvaluationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class=JobEvaluationSerializer; queryset=JobEvaluation.objects.select_related('job').all()
    def get_queryset(self): return JobEvaluation.objects.select_related('job').filter(job__in=accessible_jobs(self.request.user))

class NoteViewSet(viewsets.GenericViewSet):
    serializer_class=ApplicationNoteSerializer; queryset=ApplicationNote.objects.all()
    def get_queryset(self): return ApplicationNote.objects.select_related('job').filter(job__in=accessible_jobs(self.request.user))
    def destroy(self, request, pk=None): self.get_object().delete(); return Response(status=204)

class FollowUpViewSet(viewsets.ModelViewSet):
    serializer_class=FollowUpSerializer; queryset=FollowUp.objects.select_related('job').all()
    http_method_names=['get','patch','head','options']
    def get_queryset(self): return FollowUp.objects.select_related('job').filter(job__in=accessible_jobs(self.request.user))

@api_view(['POST'])
def bulk_create_jobs(request):
    pasted=(request.data.get('url') or '') + '\n' + (request.data.get('raw_description') or '')
    links=extract_links(pasted)
    if not links:
        if (request.data.get('url') or '').strip() and not any((request.data.get(f) or '').strip() for f in ['company','title','raw_description']):
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
    for i, link in enumerate(links):
        if action_map and i not in action_map:
            continue
        data=request.data.copy(); data['url']=link; data['company']=data.get('company') or 'Unknown company'; data['title']=data.get('title') or 'Untitled role'
        if len(links)>1 and (not request.data.get('title')): data['title']=f'Untitled role {i+1}'
        existing=find_existing_by_url(link, queryset=owned_qs) if link else None
        action=action_map.get(i) or strategy
        if existing and action=='skip':
            skipped.append({'index':i,'url':link}); continue
        if existing and action=='override':
            for f in ['company','title','location','url','source','raw_description','salary_info','language_requirements','work_mode']:
                if data.get(f): setattr(existing,f,clean_job_location(data.get(f)) if f=='location' else data.get(f))
            for k,v in job_create_defaults(request.user).items(): setattr(existing,k,v)
            existing.save(); updated.append(JobLeadSerializer(existing).data); continue
        if existing and action=='duplicate': data['title']=duplicate_title(data.get('title') or 'Untitled role', owned_qs)
        ser=JobLeadSerializer(data=data); ser.is_valid(raise_exception=True); obj=ser.save(**job_create_defaults(request.user)); created.append(JobLeadSerializer(obj).data)
    remaining=[c for c in conflicts if c['index'] not in action_map]
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
    if profile and profile.requested_submit_for_id and not profile.submit_for_id:
        return Response({'detail':'Your friend has not approved this submission link yet.'}, status=403)
    owner=profile.submit_for if profile and profile.submit_for_id else (request.user if request.user.is_authenticated else None)
    links=extract_links((request.data.get('url') or '') + '\n' + (request.data.get('raw_description') or '')) or ['']
    strategy=request.data.get('duplicate_strategy') or request.data.get('duplicate_action')
    action_map={a.get('index'):a.get('action') for a in request.data.get('duplicate_actions',[])}
    conflicts=[]; created=[]; skipped=[]
    for i, link in enumerate(links):
        existing=find_existing_by_url(link, owner)
        action=action_map.get(i) or strategy
        if existing and not action:
            conflicts.append({'index':i,'url':link,'incoming':{'company':request.data.get('company') or 'Unknown company','title':request.data.get('title') or 'Untitled role'},'existing_jobs':[JobLeadSerializer(existing).data]})
    if conflicts and not action_map:
        return Response({'ok':False,'type':'duplicate_conflicts','message':'Some links already exist in this dashboard. Choose which ones to duplicate or skip.','conflicts':conflicts}, status=400)
    for i, link in enumerate(links):
        existing=find_existing_by_url(link, owner) if link else None
        action=action_map.get(i) or strategy
        if action_map and i not in action_map: continue
        if existing and action!='duplicate': skipped.append({'index':i,'url':link}); continue
        data=request.data.copy(); data['url']=link; data['company']=data.get('company') or 'Unknown company'; data['title']=data.get('title') or ('Untitled role' if len(links)==1 else f'Untitled role {i+1}')
        if existing and action=='duplicate': data['title']=duplicate_title(data.get('title') or 'Untitled role', JobLead.objects.filter(Q(created_by=owner)|Q(submitted_for=owner)) if owner else None)
        ser=PublicSubmissionSerializer(data=data); ser.is_valid(raise_exception=True)
        job=ser.save()
        if request.user.is_authenticated:
            job.created_by=request.user; job.submitted_for=profile.submit_for if profile else None; job.save(update_fields=['created_by','submitted_for'])
        created.append(JobLeadSerializer(job).data)
    remaining=[c for c in conflicts if c['index'] not in action_map]
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

@api_view(['POST'])
@throttle_classes([ImportUserThrottle])
def import_eval(request):
    result=import_any_json(request.data.get('json') or request.data.get('pasted_json') or request.data, user=request.user)
    return Response(result, status=201 if result.get('ok') else 400)

@api_view(['GET'])
def stats(request):
    jobs=accessible_jobs(request.user)
    today=timezone.localdate(); evaluations=JobEvaluation.objects.filter(job__in=jobs)
    application_date_jobs=jobs.filter(status_date__isnull=False)
    week_start=today-timezone.timedelta(days=today.weekday())
    month_start=today.replace(day=1)
    next_month=(today.replace(year=today.year+1, month=1, day=1) if today.month == 12 else today.replace(month=today.month+1, day=1))
    month_end=next_month-timezone.timedelta(days=1)
    weekly_applications=[]
    for i in range(3,-1,-1):
        start=week_start-timezone.timedelta(days=i*7)
        end=start+timezone.timedelta(days=6)
        weekly_applications.append({'label':start.strftime('%d %b'), 'start':start.isoformat(), 'end':end.isoformat(), 'count':application_date_jobs.filter(status_date__gte=start, status_date__lte=end).count()})
    month_week_applications=[]
    suffixes=['st','nd','rd']
    cursor=month_start
    idx=1
    while cursor <= month_end:
        end=min(cursor+timezone.timedelta(days=6), month_end)
        suffix=suffixes[idx-1] if idx <= 3 else 'th'
        month_week_applications.append({'label':f'{idx}{suffix} week', 'range':f'{cursor.day}-{end.day} {end.strftime("%b")}', 'start':cursor.isoformat(), 'end':end.isoformat(), 'count':application_date_jobs.filter(status_date__gte=cursor, status_date__lte=end).count()})
        cursor=end+timezone.timedelta(days=1)
        idx+=1
    workday_applications=[]
    cursor=month_start
    while cursor <= month_end:
        if cursor.weekday() < 5:
            workday_applications.append({'label':cursor.strftime('%d %b'), 'date':cursor.isoformat(), 'count':application_date_jobs.filter(status_date=cursor).count()})
        cursor+=timezone.timedelta(days=1)
    applications_this_week=application_date_jobs.filter(status_date__gte=week_start, status_date__lte=today).count()
    elapsed_workdays=sum(1 for i in range(min(today.weekday(), 4)+1))
    return Response({'total_jobs':jobs.count(), 'jobs_by_status':dict(jobs.values_list('status').annotate(c=Count('id'))), 'average_fit_score':evaluations.aggregate(a=Avg('fit_score'))['a'] or 0, 'high_priority_jobs':evaluations.filter(priority='high', job__status='new').values('job').distinct().count(), 'applications_sent':jobs.filter(status='applied').count(), 'applications_this_week':applications_this_week, 'applications_per_workday':round(applications_this_week/max(elapsed_workdays,1), 1), 'workday_applications':workday_applications, 'month_week_applications':month_week_applications, 'weekly_applications':weekly_applications, 'interviews':jobs.filter(status='interview').count(), 'rejected':jobs.filter(status='rejected').count(), 'jobs_needing_follow_up':FollowUp.objects.filter(job__in=jobs, completed=False, follow_up_date__lte=today).count()})

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
