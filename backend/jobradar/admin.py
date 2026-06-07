from datetime import timedelta

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth import get_user_model
from django.db.models import Count, Max, Q, Sum
from django.utils import timezone
from django.utils.html import format_html
from .models import JobLead, JobEvaluation, ApplicationNote, FollowUp, InviteCode, UserDailyUsage, UserProfile

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
    list_display=('username','email','is_staff','is_active','last_login','date_joined','usage_today','usage_week','usage_month','usage_total','job_count','note_count','last_used_at')
    list_filter=UserAdmin.list_filter + ('last_login','date_joined')
    search_fields=('username','email')
    readonly_fields=UserAdmin.readonly_fields + ('usage_today','usage_week','usage_month','usage_total','usage_graph','job_count','note_count','last_job_update','last_note_at','last_used_at')
    fieldsets=UserAdmin.fieldsets + (
        ('DACHApply usage', {'fields': ('usage_today','usage_week','usage_month','usage_total','usage_graph','job_count','note_count','last_job_update','last_note_at','last_used_at')}),
    )

    def _usage_stats(self, obj):
        if hasattr(obj, '_jobradar_admin_usage_stats'):
            return obj._jobradar_admin_usage_stats
        jobs=JobLead.objects.filter(Q(created_by=obj)|Q(submitted_for=obj)).distinct()
        job_stats=jobs.aggregate(count=Count('id'), last=Max('updated_at'))
        note_stats=ApplicationNote.objects.filter(created_by=obj).aggregate(count=Count('id'), last=Max('created_at'))
        daily=self._daily_usage_stats(obj)
        candidates=[obj.last_login, job_stats['last'], note_stats['last'], daily['last_seen_at']]
        obj._jobradar_admin_usage_stats={
            'job_count': job_stats['count'] or 0,
            'note_count': note_stats['count'] or 0,
            'last_job_update': job_stats['last'],
            'last_note_at': note_stats['last'],
            'last_used_at': max([value for value in candidates if value], default=None),
        }
        return obj._jobradar_admin_usage_stats

    def _daily_usage_stats(self, obj):
        if hasattr(obj, '_jobradar_admin_daily_usage_stats'):
            return obj._jobradar_admin_daily_usage_stats
        today=timezone.localdate()
        week_start=today - timedelta(days=6)
        month_start=today - timedelta(days=29)
        qs=UserDailyUsage.objects.filter(user=obj)
        rows={row.date: row.request_count for row in qs.filter(date__gte=month_start)}
        stats={
            'today': rows.get(today, 0),
            'week': qs.filter(date__gte=week_start).aggregate(total=Sum('request_count'))['total'] or 0,
            'month': qs.filter(date__gte=month_start).aggregate(total=Sum('request_count'))['total'] or 0,
            'total': qs.aggregate(total=Sum('request_count'))['total'] or 0,
            'last_seen_at': qs.aggregate(last=Max('last_seen_at'))['last'],
            'rows': rows,
            'month_start': month_start,
            'today': today,
        }
        obj._jobradar_admin_daily_usage_stats=stats
        return stats

    @admin.display(description='Today')
    def usage_today(self, obj):
        return self._daily_usage_stats(obj)['today']

    @admin.display(description='7 days')
    def usage_week(self, obj):
        return self._daily_usage_stats(obj)['week']

    @admin.display(description='30 days')
    def usage_month(self, obj):
        return self._daily_usage_stats(obj)['month']

    @admin.display(description='Total usage')
    def usage_total(self, obj):
        return self._daily_usage_stats(obj)['total']

    @admin.display(description='Usage graph')
    def usage_graph(self, obj):
        stats=self._daily_usage_stats(obj)
        start=stats['month_start']
        values=[]
        for offset in range(30):
            day=start + timedelta(days=offset)
            values.append((day, stats['rows'].get(day, 0)))
        max_count=max([count for _, count in values], default=0) or 1
        bars=''.join(
            f'<div title="{day}: {count} requests" style="display:inline-block;width:10px;height:{max(2, int((count / max_count) * 80))}px;margin-right:3px;background:#417690;vertical-align:bottom;border-radius:2px"></div>'
            for day, count in values
        )
        return format_html(
            '<div style="min-width:360px">'
            '<div style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:10px">'
            '<strong>Today: {}</strong><strong>7 days: {}</strong><strong>30 days: {}</strong><strong>Total: {}</strong>'
            '</div>'
            '<div style="height:90px;border-left:1px solid #ddd;border-bottom:1px solid #ddd;padding:4px 0 0 4px;white-space:nowrap">{}</div>'
            '<div style="color:#666;margin-top:4px">Last 30 days; bar height = authenticated requests per day.</div>'
            '</div>',
            stats['today'], stats['week'], stats['month'], stats['total'], format_html(bars)
        )

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

@admin.register(UserDailyUsage)
class UserDailyUsageAdmin(admin.ModelAdmin):
    list_display=('user','date','request_count','last_seen_at')
    search_fields=('user__username','user__email')
    list_filter=('date',)
    date_hierarchy='date'
    readonly_fields=('created_at','updated_at')

@admin.register(InviteCode)
class InviteCodeAdmin(admin.ModelAdmin):
    list_display=('code','label','active','expires_at','created_at')
    search_fields=('code','label')
    list_filter=('active','created_at')
