from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth import get_user_model
from django.db.models import Count, Max, Q
from .models import JobLead, JobEvaluation, ApplicationNote, FollowUp, InviteCode, UserProfile

User=get_user_model()
try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass

class UserProfileInline(admin.StackedInline):
    model=UserProfile
    can_delete=False
    extra=0
    fk_name='user'

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    inlines=(UserProfileInline,)
    list_display=('username','email','is_staff','is_active','last_login','date_joined','job_count','note_count','last_job_update','last_used_at')
    list_filter=UserAdmin.list_filter + ('last_login','date_joined')
    search_fields=('username','email')
    readonly_fields=UserAdmin.readonly_fields + ('job_count','note_count','last_job_update','last_note_at','last_used_at')
    fieldsets=UserAdmin.fieldsets + (
        ('DACHApply usage', {'fields': ('job_count','note_count','last_job_update','last_note_at','last_used_at')}),
    )

    def _usage_stats(self, obj):
        if hasattr(obj, '_jobradar_admin_usage_stats'):
            return obj._jobradar_admin_usage_stats
        jobs=JobLead.objects.filter(Q(created_by=obj)|Q(submitted_for=obj)).distinct()
        job_stats=jobs.aggregate(count=Count('id'), last=Max('updated_at'))
        note_stats=ApplicationNote.objects.filter(created_by=obj).aggregate(count=Count('id'), last=Max('created_at'))
        candidates=[obj.last_login, job_stats['last'], note_stats['last']]
        obj._jobradar_admin_usage_stats={
            'job_count': job_stats['count'] or 0,
            'note_count': note_stats['count'] or 0,
            'last_job_update': job_stats['last'],
            'last_note_at': note_stats['last'],
            'last_used_at': max([value for value in candidates if value], default=None),
        }
        return obj._jobradar_admin_usage_stats

    @admin.display(description='Jobs')
    def job_count(self, obj):
        return self._usage_stats(obj)['job_count']

    @admin.display(description='Notes')
    def note_count(self, obj):
        return self._usage_stats(obj)['note_count']

    @admin.display(description='Last job update')
    def last_job_update(self, obj):
        return self._usage_stats(obj)['last_job_update']

    @admin.display(description='Last note')
    def last_note_at(self, obj):
        return self._usage_stats(obj)['last_note_at']

    @admin.display(description='Last used')
    def last_used_at(self, obj):
        return self._usage_stats(obj)['last_used_at']

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display=('user','submit_for','requested_submit_for','created_at')
    search_fields=('user__username','submit_for__username','requested_submit_for__username')
    list_filter=('created_at',)

@admin.register(JobLead)
class JobLeadAdmin(admin.ModelAdmin):
    list_display=('company','title','location','work_mode','status','url','created_at')
    search_fields=('company','title','url','raw_description')
    list_filter=('status','work_mode','created_at')

@admin.register(JobEvaluation)
class JobEvaluationAdmin(admin.ModelAdmin):
    list_display=('job','fit_score','priority','recommendation','created_at')
    list_filter=('priority','recommendation','created_at')
    search_fields=('job__company','job__title','summary')

@admin.register(ApplicationNote)
class ApplicationNoteAdmin(admin.ModelAdmin):
    list_display=('job','note_type','created_by','created_at')
    search_fields=('job__company','job__title','note')
    list_filter=('note_type','created_at')

@admin.register(FollowUp)
class FollowUpAdmin(admin.ModelAdmin):
    list_display=('job','follow_up_date','reason','completed')
    list_filter=('completed','follow_up_date')
    search_fields=('job__company','job__title','reason')

@admin.register(InviteCode)
class InviteCodeAdmin(admin.ModelAdmin):
    list_display=('code','label','active','expires_at','created_at')
    search_fields=('code','label')
    list_filter=('active','created_at')
