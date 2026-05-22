from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth import get_user_model
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
    list_display=('username','email','is_staff','is_active','date_joined')
    search_fields=('username','email')

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
