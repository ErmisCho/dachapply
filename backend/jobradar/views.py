from django.contrib.auth import authenticate, login, logout
from django.db.models import Avg, Count, Q
from django.http import HttpResponse
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import viewsets, status
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from .models import JobLead, JobEvaluation, ApplicationNote, FollowUp
from .serializers import JobLeadSerializer, JobEvaluationSerializer, ApplicationNoteSerializer, FollowUpSerializer, PublicSubmissionSerializer
from .services.prompt_builder import build_prompt, build_enrichment_prompt, build_bulk_links_prompt
from .services.json_importer import import_any_json
from .services.exporters import jobs_json, jobs_csv, chatgpt_brief

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
        return qs.distinct()
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
@permission_classes([AllowAny])
def public_submit(request):
    ser=PublicSubmissionSerializer(data=request.data); ser.is_valid(raise_exception=True); job=ser.save(); return Response(JobLeadSerializer(job).data, status=201)

@api_view(['POST'])
def generate_prompt(request):
    ids=request.data.get('job_ids') or []
    jobs=JobLead.objects.filter(id__in=ids)
    if not ids or jobs.count()!=len(set(ids)): return Response({'detail':'Provide valid job_ids'}, status=400)
    return Response({'generated_prompt': build_prompt(jobs, request.data.get('custom_instructions',''))})

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
