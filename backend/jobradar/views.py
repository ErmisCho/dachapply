from django.contrib.auth import authenticate, login, logout, get_user_model
from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.db.models import Avg, Case, Count, IntegerField, Q, Value, When
from django.http import HttpResponse
from django.utils import timezone
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import viewsets, status
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from .models import JobLead, JobEvaluation, ApplicationNote, FollowUp, UserProfile, InviteCode
from .serializers import JobLeadSerializer, JobEvaluationSerializer, ApplicationNoteSerializer, FollowUpSerializer, PublicSubmissionSerializer, normalize_job_url
from .services.prompt_builder import build_prompt, build_enrichment_prompt, build_bulk_links_prompt, build_combined_prompt
from .services.json_importer import import_any_json, duplicate_title
from .services.exporters import jobs_json, jobs_csv, chatgpt_brief
from .services.user_data_portability import APP_NAME, SCHEMA_VERSION, build_user_export, export_user_data_csv, export_user_data_xlsx, import_user_export, parse_import_payload


def find_existing_by_url(url, owner=None):
    if not url: return None
    url=normalize_job_url(url)
    variants={url, url.rstrip('/')}
    if not url.endswith('/'): variants.add(url + '/')
    qs=JobLead.objects.filter(url__in=variants)
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

@ensure_csrf_cookie
@api_view(['GET'])
@permission_classes([AllowAny])
def csrf(request): return Response({'detail':'ok'})

@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    user=authenticate(request, username=request.data.get('username'), password=request.data.get('password'))
    if not user: return Response({'detail':'Invalid credentials'}, status=400)
    login(request, user); return Response({'username':user.username})

@api_view(['POST'])
@permission_classes([AllowAny])
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
@permission_classes([AllowAny])
def password_reset_request(request):
    email=(request.data.get('email') or '').strip().lower()
    User=get_user_model(); user=User.objects.filter(email__iexact=email).first()
    if user:
        uid=urlsafe_base64_encode(force_bytes(user.pk)); token=default_token_generator.make_token(user)
        link=f"{settings.FRONTEND_URL}/reset-password/{uid}/{token}"
        send_mail('Reset your DACHApply password', f'Use this link to reset your password:\n\n{link}', settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False)
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

class JobLeadViewSet(viewsets.ModelViewSet):
    serializer_class=JobLeadSerializer
    queryset=JobLead.objects.all().prefetch_related('evaluations')
    def get_queryset(self):
        qs=super().get_queryset(); p=self.request.query_params
        profile=getattr(self.request.user, 'jobradar_profile', None)
        if profile and (profile.submit_for_id or profile.requested_submit_for_id):
            qs=qs.filter(created_by=self.request.user, submitted_for=profile.submit_for, source='friend')
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
        existing=find_existing_by_url(url)
        if existing and not action:
            return Response({'ok':False,'type':'duplicate_conflicts','message':'This job link already exists.','conflicts':[{'index':0,'url':url,'incoming':{'company':ser.validated_data.get('company') or 'Unknown company','title':ser.validated_data.get('title') or 'Untitled role'},'existing_jobs':[JobLeadSerializer(existing).data]}]}, status=400)
        if existing and action=='override':
            for k,v in ser.validated_data.items(): setattr(existing,k,v)
            existing.created_by=request.user; existing.save(); return Response(JobLeadSerializer(existing).data)
        if existing and action=='duplicate':
            ser.validated_data['title']=duplicate_title(ser.validated_data.get('title') or 'Untitled role')
        if existing and action=='skip': return Response(JobLeadSerializer(existing).data)
        obj=ser.save(created_by=request.user); return Response(JobLeadSerializer(obj).data, status=201)
    def perform_create(self, serializer): serializer.save(created_by=self.request.user)
    def destroy(self, request, pk=None):
        qs=JobLead.objects.all()
        profile=getattr(request.user, 'jobradar_profile', None)
        if profile and (profile.submit_for_id or profile.requested_submit_for_id):
            qs=qs.filter(created_by=request.user, submitted_for=profile.submit_for, source='friend')
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
        ser=JobEvaluationSerializer(data={**request.data, 'job': job.id}); ser.is_valid(raise_exception=True); ser.save(); return Response(ser.data, status=201)
    @action(detail=True, methods=['get','post'])
    def notes(self, request, pk=None):
        job=self.get_object()
        if request.method=='GET': return Response(ApplicationNoteSerializer(job.notes.all(), many=True).data)
        ser=ApplicationNoteSerializer(data={**request.data,'job':job.id}); ser.is_valid(raise_exception=True); ser.save(created_by=request.user); return Response(ser.data, status=201)
    @action(detail=True, methods=['get','post'])
    def followups(self, request, pk=None):
        job=self.get_object()
        if request.method=='GET': return Response(FollowUpSerializer(job.followups.all(), many=True).data)
        ser=FollowUpSerializer(data={**request.data,'job':job.id}); ser.is_valid(raise_exception=True); ser.save(); return Response(ser.data, status=201)

class EvaluationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class=JobEvaluationSerializer; queryset=JobEvaluation.objects.select_related('job').all()

class NoteViewSet(viewsets.GenericViewSet):
    serializer_class=ApplicationNoteSerializer; queryset=ApplicationNote.objects.all()
    def destroy(self, request, pk=None): self.get_object().delete(); return Response(status=204)

class FollowUpViewSet(viewsets.ModelViewSet):
    serializer_class=FollowUpSerializer; queryset=FollowUp.objects.select_related('job').all()
    http_method_names=['get','patch','head','options']

@api_view(['POST'])
def bulk_create_jobs(request):
    links=extract_links((request.data.get('url') or '') + '\n' + (request.data.get('raw_description') or ''))
    if not links:
        links=['']
    conflicts=[]; created=[]; updated=[]; skipped=[]
    strategy=request.data.get('duplicate_action') or request.data.get('duplicate_strategy')
    action_map={a.get('index'):a.get('action') for a in request.data.get('duplicate_actions',[])}
    for i, link in enumerate(links):
        existing=find_existing_by_url(link) if link else None
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
        existing=find_existing_by_url(link) if link else None
        action=action_map.get(i) or strategy
        if existing and action=='skip':
            skipped.append({'index':i,'url':link}); continue
        if existing and action=='override':
            for f in ['company','title','location','url','source','raw_description','salary_info','language_requirements','work_mode']:
                if data.get(f): setattr(existing,f,data.get(f))
            existing.created_by=request.user; existing.save(); updated.append(JobLeadSerializer(existing).data); continue
        if existing and action=='duplicate': data['title']=duplicate_title(data.get('title') or 'Untitled role')
        ser=JobLeadSerializer(data=data); ser.is_valid(raise_exception=True); obj=ser.save(created_by=request.user); created.append(JobLeadSerializer(obj).data)
    remaining=[c for c in conflicts if c['index'] not in action_map]
    if remaining:
        return Response({'ok':False,'type':'duplicate_conflicts','message':'One or more job links still need a duplicate choice.','conflicts':remaining,'created':created,'updated':updated,'skipped':skipped}, status=400)
    return Response({'ok':True,'count':len(created)+len(updated),'created':created,'updated':updated,'skipped':skipped}, status=201)

@api_view(['POST'])
@permission_classes([AllowAny])
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
        if existing and action=='duplicate': data['title']=duplicate_title(data.get('title') or 'Untitled role')
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
    jobs=JobLead.objects.filter(id__in=ids)
    if not ids or jobs.count()!=len(set(ids)): return Response({'detail':'Provide valid job_ids'}, status=400)
    return Response({'generated_prompt': build_prompt(jobs, request.data.get('custom_instructions',''))})

@api_view(['POST'])
def generate_combined_prompt(request):
    ids=request.data.get('job_ids') or []
    jobs=JobLead.objects.filter(id__in=ids)
    if not ids or jobs.count()!=len(set(ids)): return Response({'detail':'Provide valid job_ids'}, status=400)
    return Response({'generated_prompt': build_combined_prompt(jobs, request.data.get('custom_instructions',''))})

@api_view(['POST'])
def generate_bulk_links_prompt(request):
    raw=request.data.get('links') or request.data.get('text') or ''
    links=[x.strip() for x in raw.replace(',', '\n').splitlines() if x.strip()]
    if not links: return Response({'detail':'Provide one or more links'}, status=400)
    return Response({'generated_prompt': build_bulk_links_prompt(links, request.data.get('custom_instructions',''))})

@api_view(['POST'])
def generate_enrichment_prompt(request):
    ids=request.data.get('job_ids') or []
    if ids:
        jobs=JobLead.objects.filter(id__in=ids)
        if jobs.count()!=len(set(ids)): return Response({'detail':'Provide valid job_ids'}, status=400)
    else:
        jobs=JobLead.objects.filter(Q(company__in=['','Unknown company'])|Q(title__in=['','Untitled role'])|Q(raw_description=''))[:25]
    if not jobs: return Response({'detail':'No jobs need detail enrichment'}, status=400)
    return Response({'generated_prompt': build_enrichment_prompt(jobs, request.data.get('custom_instructions',''))})

@api_view(['POST'])
def import_eval(request):
    result=import_any_json(request.data.get('json') or request.data.get('pasted_json') or request.data)
    return Response(result, status=201 if result.get('ok') else 400)

@api_view(['GET'])
def stats(request):
    jobs=JobLead.objects.all(); profile=getattr(request.user, 'jobradar_profile', None)
    if profile and (profile.submit_for_id or profile.requested_submit_for_id):
        jobs=jobs.filter(created_by=request.user, submitted_for=profile.submit_for, source='friend')
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
def import_user_data(request):
    try:
        payload = parse_import_payload(request)
    except ValueError as exc:
        return Response({'created': {}, 'updated': {}, 'skipped': {}, 'errors': [str(exc)]}, status=400)
    summary = import_user_export(request.user, payload)
    return Response(summary, status=400 if summary.get('errors') or summary.get('type') == 'import_conflicts' else 200)

@api_view(['GET'])
def export_jobs_json(request): return HttpResponse(jobs_json(), content_type='application/json')
@api_view(['GET'])
def export_jobs_csv(request):
    r=HttpResponse(jobs_csv(), content_type='text/csv'); r['Content-Disposition']='attachment; filename="jobs.csv"'; return r
@api_view(['GET'])
def export_chatgpt_brief(request): return HttpResponse(chatgpt_brief(), content_type='text/markdown')
