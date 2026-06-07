from datetime import timedelta

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth import get_user_model
from django.db.models import Count, Max, Q, Sum
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from .models import JobLead, JobEvaluation, ApplicationNote, FollowUp, InviteCode, SiteDailyUsage, UserDailyUsage, UserProfile

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
    change_list_template='admin/auth/user/change_list.html'
    inlines=(UserProfileInline,)
    list_display=('username','email','is_staff','is_active','last_login','date_joined','usage_today','usage_week','usage_month','usage_total','job_count','note_count','last_used_at')
    list_filter=UserAdmin.list_filter + ('last_login','date_joined')
    search_fields=('username','email')
    readonly_fields=UserAdmin.readonly_fields + ('usage_today','usage_week','usage_month','usage_total','usage_graph','job_count','note_count','last_job_update','last_note_at','last_used_at')
    fieldsets=UserAdmin.fieldsets + (
        ('DACHApply usage', {'fields': ('usage_today','usage_week','usage_month','usage_total','usage_graph','job_count','note_count','last_job_update','last_note_at','last_used_at')}),
    )

    def changelist_view(self, request, extra_context=None):
        extra_context=extra_context or {}
        extra_context['usage_overview']=self._site_usage_overview()
        return super().changelist_view(request, extra_context=extra_context)

    def _site_usage_overview(self):
        today=timezone.localdate()
        week_start=today - timedelta(days=6)
        month_start=today - timedelta(days=29)
        site_qs=SiteDailyUsage.objects.all()
        user_qs=UserDailyUsage.objects.all()
        today_stats=site_qs.filter(date=today).aggregate(total=Sum('request_count'), auth=Sum('authenticated_count'), anon=Sum('anonymous_count'))
        week_stats=site_qs.filter(date__gte=week_start).aggregate(total=Sum('request_count'), auth=Sum('authenticated_count'), anon=Sum('anonymous_count'))
        month_stats=site_qs.filter(date__gte=month_start).aggregate(total=Sum('request_count'), auth=Sum('authenticated_count'), anon=Sum('anonymous_count'))
        total_stats=site_qs.aggregate(total=Sum('request_count'), auth=Sum('authenticated_count'), anon=Sum('anonymous_count'))
        return {
            'today': today_stats['total'] or 0,
            'today_auth': today_stats['auth'] or 0,
            'today_anon': today_stats['anon'] or 0,
            'today_users': user_qs.filter(date=today).aggregate(total=Count('user', distinct=True))['total'] or 0,
            'week': week_stats['total'] or 0,
            'week_auth': week_stats['auth'] or 0,
            'week_anon': week_stats['anon'] or 0,
            'week_users': user_qs.filter(date__gte=week_start).aggregate(total=Count('user', distinct=True))['total'] or 0,
            'month': month_stats['total'] or 0,
            'month_auth': month_stats['auth'] or 0,
            'month_anon': month_stats['anon'] or 0,
            'month_users': user_qs.filter(date__gte=month_start).aggregate(total=Count('user', distinct=True))['total'] or 0,
            'total': total_stats['total'] or 0,
            'total_auth': total_stats['auth'] or 0,
            'total_anon': total_stats['anon'] or 0,
            'total_users': user_qs.aggregate(total=Count('user', distinct=True))['total'] or 0,
            'graphs_html': self._site_usage_graphs_html(site_qs),
        }

    def _month_start(self, value):
        return value.replace(day=1)

    def _add_months(self, value, months):
        month_index=value.year * 12 + value.month - 1 + months
        return value.replace(year=month_index // 12, month=month_index % 12 + 1, day=1)

    def _chart_html(self, title, subtitle, values, color):
        max_count=max([count for _, count, _ in values], default=0) or 1
        first_label=values[0][0] if values else ''
        last_label=values[-1][0] if values else ''
        bars=''.join(
            f'<div title="{label}: {count} requests{detail_text}" style="display:inline-block;width:10px;height:{max(2, int((count / max_count) * 90))}px;margin-right:3px;background:{color};vertical-align:bottom;border-radius:2px"></div>'
            for label, count, detail_text in values
        )
        return (
            '<div style="border:1px solid var(--hairline-color,#ddd);border-radius:6px;padding:10px;background:var(--body-bg,#fff);min-width:280px;flex:1">'
            f'<h3 style="margin:0 0 4px 0">{title}</h3>'
            f'<div style="color:var(--quiet-color,#666);margin-bottom:8px">{subtitle}</div>'
            '<div style="height:100px;border-left:1px solid var(--hairline-color,#ddd);border-bottom:1px solid var(--hairline-color,#ddd);padding:4px 0 0 4px;white-space:nowrap;overflow:hidden">'
            f'{bars}'
            '</div>'
            f'<div style="display:flex;justify-content:space-between;color:var(--quiet-color,#666);font-size:11px;margin-top:4px"><span>{first_label}</span><span>{last_label}</span></div>'
            '<div style="color:var(--quiet-color,#666);font-size:11px;margin-top:2px">Hover a bar for the exact day/week/month.</div>'
            '</div>'
        )

    def _site_usage_graphs_html(self, qs):
        today=timezone.localdate()
        rows=list(qs.values('date','request_count','authenticated_count','anonymous_count'))

        def detail(matching):
            auth=sum(row['authenticated_count'] for row in matching)
            anon=sum(row['anonymous_count'] for row in matching)
            return f', authenticated: {auth}, anonymous: {anon}'

        daily_start=today - timedelta(days=29)
        daily=[]
        for offset in range(30):
            day=daily_start + timedelta(days=offset)
            matching=[row for row in rows if row['date'] == day]
            daily.append((day.isoformat(), sum(row['request_count'] for row in matching), detail(matching)))

        weekly_start=today - timedelta(days=83)
        weekly=[]
        for offset in range(12):
            start=weekly_start + timedelta(days=offset * 7)
            end=start + timedelta(days=6)
            matching=[row for row in rows if start <= row['date'] <= end]
            weekly.append((f'week {start.isoformat()} to {end.isoformat()}', sum(row['request_count'] for row in matching), detail(matching)))

        month_start=self._add_months(self._month_start(today), -11)
        monthly=[]
        for offset in range(12):
            start=self._add_months(month_start, offset)
            end=self._add_months(start, 1)
            matching=[row for row in rows if start <= row['date'] < end]
            monthly.append((start.strftime('%Y-%m'), sum(row['request_count'] for row in matching), detail(matching)))

        first_date=min([row['date'] for row in rows], default=month_start)
        total_start=self._month_start(first_date)
        month_count=(today.year - total_start.year) * 12 + today.month - total_start.month + 1
        if month_count > 24:
            visible_start=self._add_months(self._month_start(today), -23)
            running_total=sum(row['request_count'] for row in rows if row['date'] < visible_start)
            month_count=24
        else:
            visible_start=total_start
            running_total=0
        total=[]
        for offset in range(month_count):
            start=self._add_months(visible_start, offset)
            end=self._add_months(start, 1)
            matching=[row for row in rows if start <= row['date'] < end]
            running_total += sum(row['request_count'] for row in matching)
            auth_total=sum(row['authenticated_count'] for row in rows if row['date'] < end)
            anon_total=sum(row['anonymous_count'] for row in rows if row['date'] < end)
            total.append((start.strftime('%Y-%m'), running_total, f', authenticated total: {auth_total}, anonymous total: {anon_total}'))

        html=(
            '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:12px;min-width:640px">'
            + self._chart_html('Daily usage', 'All requests per day, last 30 days', daily, '#417690')
            + self._chart_html('Weekly usage', 'All requests per 7-day week, last 12 weeks', weekly, '#79aec8')
            + self._chart_html('Monthly usage', 'All requests per calendar month, last 12 months', monthly, '#609ab6')
            + self._chart_html('Total usage', 'Cumulative all requests by month, all time shown up to 24 months', total, '#2f5d75')
            + '</div>'
        )
        return mark_safe(html)

    def _usage_graphs_html(self, qs, include_users=False):
        today=timezone.localdate()
        rows=list(qs.values('date','request_count','user_id'))

        def user_text(user_ids):
            if not include_users:
                return ''
            count=len(user_ids)
            return f', {count} user' + ('' if count == 1 else 's')

        daily_start=today - timedelta(days=29)
        daily=[]
        for offset in range(30):
            day=daily_start + timedelta(days=offset)
            matching=[row for row in rows if row['date'] == day]
            daily.append((day.isoformat(), sum(row['request_count'] for row in matching), user_text({row['user_id'] for row in matching})))

        weekly_start=today - timedelta(days=83)
        weekly=[]
        for offset in range(12):
            start=weekly_start + timedelta(days=offset * 7)
            end=start + timedelta(days=6)
            matching=[row for row in rows if start <= row['date'] <= end]
            weekly.append((f'{start.isoformat()} to {end.isoformat()}', sum(row['request_count'] for row in matching), user_text({row['user_id'] for row in matching})))

        month_start=self._add_months(self._month_start(today), -11)
        monthly=[]
        for offset in range(12):
            start=self._add_months(month_start, offset)
            end=self._add_months(start, 1)
            matching=[row for row in rows if start <= row['date'] < end]
            monthly.append((start.strftime('%Y-%m'), sum(row['request_count'] for row in matching), user_text({row['user_id'] for row in matching})))

        first_date=min([row['date'] for row in rows], default=month_start)
        total_start=self._month_start(first_date)
        month_count=(today.year - total_start.year) * 12 + today.month - total_start.month + 1
        if month_count > 24:
            visible_start=self._add_months(self._month_start(today), -23)
            running_total=sum(row['request_count'] for row in rows if row['date'] < visible_start)
            month_count=24
        else:
            visible_start=total_start
            running_total=0
        total=[]
        for offset in range(month_count):
            start=self._add_months(visible_start, offset)
            end=self._add_months(start, 1)
            matching=[row for row in rows if start <= row['date'] < end]
            running_total += sum(row['request_count'] for row in matching)
            total.append((start.strftime('%Y-%m'), running_total, user_text({row['user_id'] for row in rows if row['date'] < end})))

        html=(
            '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:12px;min-width:640px">'
            + self._chart_html('Daily usage', 'Authenticated requests per day, last 30 days', daily, '#417690')
            + self._chart_html('Weekly usage', 'Authenticated requests per 7-day period, last 12 weeks', weekly, '#79aec8')
            + self._chart_html('Monthly usage', 'Authenticated requests per month, last 12 months', monthly, '#609ab6')
            + self._chart_html('Total usage', 'Cumulative authenticated requests by month, all time shown up to 24 months', total, '#2f5d75')
            + '</div>'
        )
        return mark_safe(html)

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

    @admin.display(description='Usage graphs')
    def usage_graph(self, obj):
        stats=self._daily_usage_stats(obj)
        return format_html(
            '<div style="min-width:700px">'
            '<div style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:10px">'
            '<strong>Today: {}</strong><strong>7 days: {}</strong><strong>30 days: {}</strong><strong>Total: {}</strong>'
            '</div>{}</div>',
            stats['today'], stats['week'], stats['month'], stats['total'], self._usage_graphs_html(UserDailyUsage.objects.filter(user=obj))
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

@admin.register(SiteDailyUsage)
class SiteDailyUsageAdmin(admin.ModelAdmin):
    list_display=('date','request_count','authenticated_count','anonymous_count','last_seen_at')
    list_filter=('date',)
    date_hierarchy='date'
    readonly_fields=('created_at','updated_at')

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
