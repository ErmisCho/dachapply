from django.contrib.auth import authenticate, login, logout
from django.db.models import Avg, Case, Count, IntegerField, Q, Value, When
from django.http import HttpResponse
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import viewsets, status
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from .models import JobLead, JobEvaluation, ApplicationNote, FollowUp
from .serializers import JobLeadSerializer, JobEvaluationSerializer, ApplicationNoteSerializer, FollowUpSerializer, PublicSubmissionSerializer, normalize_job_url
from .services.prompt_builder import build_prompt, build_enrichment_prompt, build_bulk_links_prompt, build_combined_prompt
from .services.json_importer import import_any_json, duplicate_title
from .services.exporters import jobs_json, jobs_csv, chatgpt_brief


def find_existing_by_url(url):
    if not url: return None
    url=normalize_job_url(url)
    variants={url, url.rstrip('/')}
    if not url.endswith('/'): variants.add(url + '/')
    return JobLead.objects.filter(url__in=variants).first()


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
def logout_view(request): logout(request); return Response({'detail':'logged out'})

@api_view(['GET'])
def me(request): return Response({'username':request.user.username, 'is_staff':request.user.is_staff})

class JobLeadViewSet(viewsets.ModelViewSet):
    serializer_class=JobLeadSerializer
    queryset=JobLead.objects.all().prefetch_related('evaluations')
    def get_queryset(self):
        qs=super().get_queryset(); p=self.request.query_params
        if p.get('status'): qs=qs.filter(status=p['status'])
        if p.get('work_mode'): qs=qs.filter(work_mode=p['work_mode'])
        if p.get('company'): qs=qs.filter(company__icontains=p['company'])
        if p.get('location'): qs=qs.filter(location__icontains=p['location'])
        if p.get('priority'): qs=qs.filter(evaluations__priority=p['priority'])
        if p.get('recommendation'): qs=qs.filter(evaluations__recommendation=p['recommendation'])
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
    conflicts=[]; created=[]; updated=[]; action=request.data.get('duplicate_action') or request.data.get('duplicate_strategy')
    for i, link in enumerate(links):
        existing=find_existing_by_url(link) if link else None
        if existing and not action:
            conflicts.append({'index':i,'url':link,'incoming':{'company':request.data.get('company') or 'Unknown company','title':request.data.get('title') or 'Untitled role'},'existing_jobs':[JobLeadSerializer(existing).data]})
    if conflicts:
        return Response({'ok':False,'type':'duplicate_conflicts','message':'One or more job links already exist. Nothing was added yet.','conflicts':conflicts}, status=400)
    for i, link in enumerate(links):
        data=request.data.copy(); data['url']=link; data['company']=data.get('company') or 'Unknown company'; data['title']=data.get('title') or 'Untitled role'
        if len(links)>1 and (not request.data.get('title')): data['title']=f'Untitled role {i+1}'
        existing=find_existing_by_url(link) if link else None
        if existing and action=='skip': continue
        if existing and action=='override':
            for f in ['company','title','location','url','source','raw_description','salary_info','language_requirements','work_mode']:
                if data.get(f): setattr(existing,f,data.get(f))
            existing.save(); updated.append(JobLeadSerializer(existing).data); continue
        if existing and action=='duplicate': data['title']=duplicate_title(data.get('title') or 'Untitled role')
        ser=JobLeadSerializer(data=data); ser.is_valid(raise_exception=True); obj=ser.save(created_by=request.user); created.append(JobLeadSerializer(obj).data)
    return Response({'ok':True,'count':len(created)+len(updated),'created':created,'updated':updated}, status=201)

@api_view(['POST'])
@permission_classes([AllowAny])
def public_submit(request):
    ser=PublicSubmissionSerializer(data=request.data); ser.is_valid(raise_exception=True)
    url=ser.validated_data.get('url'); action=request.data.get('duplicate_action')
    existing=find_existing_by_url(url)
    if existing and not action:
        return Response({'ok':False,'type':'duplicate_conflicts','message':'This job link already exists.','conflicts':[{'index':0,'url':url,'incoming':{'company':ser.validated_data.get('company') or 'Unknown company','title':ser.validated_data.get('title') or 'Untitled role'},'existing_jobs':[JobLeadSerializer(existing).data]}]}, status=400)
    if existing and action=='override':
        data=dict(ser.validated_data); data.pop('invite_code',None); data.pop('website',None)
        for k,v in data.items(): setattr(existing,k,v or getattr(existing,k))
        existing.save(); return Response(JobLeadSerializer(existing).data)
    if existing and action=='skip': return Response(JobLeadSerializer(existing).data)
    job=ser.save()
    if existing and action=='duplicate': job.title=duplicate_title(job.title); job.save(update_fields=['title'])
    return Response(JobLeadSerializer(job).data, status=201)

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
    jobs=JobLead.objects.all(); today=timezone.localdate()
    return Response({'total_jobs':jobs.count(), 'jobs_by_status':dict(jobs.values_list('status').annotate(c=Count('id'))), 'average_fit_score':JobEvaluation.objects.aggregate(a=Avg('fit_score'))['a'] or 0, 'high_priority_jobs':JobEvaluation.objects.filter(priority='high').values('job').distinct().count(), 'applications_sent':jobs.filter(status='applied').count(), 'interviews':jobs.filter(status='interview').count(), 'rejected':jobs.filter(status='rejected').count(), 'jobs_needing_follow_up':FollowUp.objects.filter(completed=False, follow_up_date__lte=today).count()})

@api_view(['GET'])
def export_jobs_json(request): return HttpResponse(jobs_json(), content_type='application/json')
@api_view(['GET'])
def export_jobs_csv(request):
    r=HttpResponse(jobs_csv(), content_type='text/csv'); r['Content-Disposition']='attachment; filename="jobs.csv"'; return r
@api_view(['GET'])
def export_chatgpt_brief(request): return HttpResponse(chatgpt_brief(), content_type='text/markdown')
