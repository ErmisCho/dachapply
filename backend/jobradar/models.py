from django.conf import settings
from django.db import models
from django.utils import timezone

DEFAULT_CANDIDATE_PROFILE = '''Software Engineer based in Vienna. Strong Python backend experience. Django, FastAPI, REST APIs, Java. RAG, semantic search, LangChain, LangGraph. Elasticsearch/OpenSearch. SQL, PostgreSQL, MySQL. Docker, Linux, Kubernetes basics, AWS basics, Azure learning in progress. RabbitMQ, Redis, async/background processing from personal projects. Enterprise background in finance, telecom, and AI/search systems. German: professional working proficiency, B2 completed, C1 in progress. English: C2 certified. Stronger fit for Python Backend, AI Engineer, RAG, Search, Data Engineering, Platform, and reliability-focused roles. Weaker fit for frontend-heavy React/TypeScript roles, pure DevOps/SRE roles, pure ML research roles, and roles requiring deep professional cloud/Spark/Terraform experience. Do not invent experience. Be honest about gaps and hiring risk.'''

class UserProfile(models.Model):
    user=models.OneToOneField(settings.AUTH_USER_MODEL, related_name='jobradar_profile', on_delete=models.CASCADE)
    submit_for=models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, related_name='friend_submitters', on_delete=models.SET_NULL)
    requested_submit_for=models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, related_name='friend_submit_requests', on_delete=models.SET_NULL)
    candidate_profile=models.TextField(blank=True, default=DEFAULT_CANDIDATE_PROFILE)
    target_roles=models.TextField(blank=True, default='')
    preferred_locations=models.TextField(blank=True, default='')
    salary_expectations=models.TextField(blank=True, default='')
    language_levels=models.TextField(blank=True, default='')
    preferred_stack=models.TextField(blank=True, default='')
    red_flags=models.TextField(blank=True, default='')
    selling_points=models.TextField(blank=True, default='')
    evaluation_prompt_template=models.TextField(blank=True, default='')
    combined_prompt_template=models.TextField(blank=True, default='')
    enrichment_prompt_template=models.TextField(blank=True, default='')
    bulk_links_prompt_template=models.TextField(blank=True, default='')
    created_at=models.DateTimeField(auto_now_add=True)
    def __str__(self): return f'{self.user} -> {self.submit_for or self.requested_submit_for or "self"}'

class JobLead(models.Model):
    WORK_MODES=[('onsite','Onsite'),('hybrid','Hybrid'),('remote','Remote'),('unknown','Unknown')]
    STATUSES=[('new','New'),('reviewed','Reviewed'),('to_apply','To apply'),('applied','Applied'),('interview','Interview'),('rejected','Rejected'),('skipped','Skipped'),('archived','Archived')]
    company=models.CharField(max_length=200, blank=True, default='Unknown company')
    title=models.CharField(max_length=250, blank=True, default='Untitled role')
    location=models.CharField(max_length=200, blank=True)
    url=models.URLField(max_length=1000, blank=True)
    source=models.CharField(max_length=120, blank=True)
    raw_description=models.TextField(blank=True)
    submitted_by=models.CharField(max_length=120, blank=True)
    submitter_reason=models.TextField(blank=True)
    salary_info=models.CharField(max_length=250, blank=True)
    language_requirements=models.CharField(max_length=250, blank=True)
    work_mode=models.CharField(max_length=20, choices=WORK_MODES, default='unknown')
    status=models.CharField(max_length=20, choices=STATUSES, default='new')
    status_date=models.DateField(null=True, blank=True)
    interview_stage=models.PositiveSmallIntegerField(null=True, blank=True)
    interview_total=models.PositiveSmallIntegerField(null=True, blank=True)
    last_update_date=models.DateField(null=True, blank=True)
    feedback_due_date=models.DateField(null=True, blank=True)
    created_by=models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    submitted_for=models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, related_name='submitted_job_leads', on_delete=models.SET_NULL)
    created_at=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)
    class Meta: ordering=['-created_at']
    def __str__(self): return f'{self.company} - {self.title}'

class JobEvaluation(models.Model):
    PRIORITIES=[('high','High'),('medium','Medium'),('low','Low')]
    RECOMMENDATIONS=[('apply','Apply'),('maybe','Maybe'),('skip','Skip')]
    job=models.ForeignKey(JobLead, related_name='evaluations', on_delete=models.CASCADE)
    fit_score=models.IntegerField()
    priority=models.CharField(max_length=10, choices=PRIORITIES)
    recommendation=models.CharField(max_length=10, choices=RECOMMENDATIONS)
    summary=models.TextField(blank=True)
    main_match_reasons=models.JSONField(default=list)
    main_gaps=models.JSONField(default=list)
    required_skills=models.JSONField(default=list)
    nice_to_have_skills=models.JSONField(default=list)
    matched_skills=models.JSONField(default=list)
    missing_skills=models.JSONField(default=list)
    cv_adjustment_notes=models.TextField(blank=True)
    interview_prep_notes=models.TextField(blank=True)
    risk_notes=models.TextField(blank=True)
    next_action=models.TextField(blank=True)
    structured_json_raw=models.JSONField(default=dict)
    created_at=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)
    class Meta: ordering=['-created_at']
    def __str__(self): return f'{self.job} ({self.fit_score})'

class ApplicationNote(models.Model):
    TYPES=[('general','General'),('cv_change','CV change'),('recruiter_message','Recruiter message'),('interview_prep','Interview prep'),('rejection_feedback','Rejection feedback'),('follow_up','Follow up')]
    job=models.ForeignKey(JobLead, related_name='notes', on_delete=models.CASCADE)
    note=models.TextField()
    note_type=models.CharField(max_length=30, choices=TYPES, default='general')
    created_by=models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta: ordering=['-created_at']

class FollowUp(models.Model):
    job=models.ForeignKey(JobLead, related_name='followups', on_delete=models.CASCADE)
    follow_up_date=models.DateField()
    reason=models.CharField(max_length=250)
    completed=models.BooleanField(default=False)
    created_at=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)
    class Meta: ordering=['completed','follow_up_date']

class InviteCode(models.Model):
    code=models.CharField(max_length=80, unique=True)
    label=models.CharField(max_length=120, blank=True)
    active=models.BooleanField(default=True)
    expires_at=models.DateTimeField(null=True, blank=True)
    created_at=models.DateTimeField(auto_now_add=True)
    def is_valid(self): return self.active and (self.expires_at is None or self.expires_at > timezone.now())
    def __str__(self): return self.label or self.code
