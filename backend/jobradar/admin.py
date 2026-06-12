from datetime import timedelta

from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth import get_user_model
from django.shortcuts import redirect
from django.urls import path
from django.db.models import Count, Max, Q, Sum
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from .models import JobLead, JobEvaluation, ApplicationNote, FollowUp, InviteCode, ScheduledTaskRun, SiteDailyUsage, SiteVisitor, UserDailyUsage, UserProfile, VisitorDailyUsage
from .services.demo_data import DEMO_PASSWORD, DEMO_USERNAME
from .services.demo_scheduler import seed_demo_if_due

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

    def get_urls(self):
        urls=super().get_urls()
        custom=[path('seed-demo/', self.admin_site.admin_view(self.seed_demo_view), name='auth_user_seed_demo')]
        return custom + urls

    def seed_demo_view(self, request):
        if request.method != 'POST':
            return redirect('..')
        _ran, _user, jobs = seed_demo_if_due(force=True)
        messages.success(request, f'Reseeded demo user {DEMO_USERNAME} / {DEMO_PASSWORD} with {len(jobs)} default jobs.')
        return redirect('../')

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
        today_stats=site_qs.filter(date=today).aggregate(total=Sum('request_count'), auth=Sum('authenticated_count'), anon=Sum('anonymous_count'), visitors=Sum('unique_visitor_count'), demo=Sum('demo_click_count'), demo_visitors=Sum('demo_unique_visitor_count'))
        week_stats=site_qs.filter(date__gte=week_start).aggregate(total=Sum('request_count'), auth=Sum('authenticated_count'), anon=Sum('anonymous_count'), demo=Sum('demo_click_count'))
        month_stats=site_qs.filter(date__gte=month_start).aggregate(total=Sum('request_count'), auth=Sum('authenticated_count'), anon=Sum('anonymous_count'), demo=Sum('demo_click_count'))
        total_stats=site_qs.aggregate(total=Sum('request_count'), auth=Sum('authenticated_count'), anon=Sum('anonymous_count'), demo=Sum('demo_click_count'))
        return {
            'today': today_stats['total'] or 0,
            'today_auth': today_stats['auth'] or 0,
            'today_anon': today_stats['anon'] or 0,
            'today_users': user_qs.filter(date=today).aggregate(total=Count('user', distinct=True))['total'] or 0,
            'today_visitors': today_stats['visitors'] or 0,
            'today_demo_clicks': today_stats['demo'] or 0,
            'today_demo_visitors': today_stats['demo_visitors'] or 0,
            'week': week_stats['total'] or 0,
            'week_auth': week_stats['auth'] or 0,
            'week_anon': week_stats['anon'] or 0,
            'week_users': user_qs.filter(date__gte=week_start).aggregate(total=Count('user', distinct=True))['total'] or 0,
            'week_visitors': VisitorDailyUsage.objects.filter(date__gte=week_start).aggregate(total=Count('visitor', distinct=True))['total'] or 0,
            'week_demo_clicks': week_stats['demo'] or 0,
            'week_demo_visitors': VisitorDailyUsage.objects.filter(date__gte=week_start, demo_click_count__gt=0).aggregate(total=Count('visitor', distinct=True))['total'] or 0,
            'month': month_stats['total'] or 0,
            'month_auth': month_stats['auth'] or 0,
            'month_anon': month_stats['anon'] or 0,
            'month_users': user_qs.filter(date__gte=month_start).aggregate(total=Count('user', distinct=True))['total'] or 0,
            'month_visitors': VisitorDailyUsage.objects.filter(date__gte=month_start).aggregate(total=Count('visitor', distinct=True))['total'] or 0,
            'month_demo_clicks': month_stats['demo'] or 0,
            'month_demo_visitors': VisitorDailyUsage.objects.filter(date__gte=month_start, demo_click_count__gt=0).aggregate(total=Count('visitor', distinct=True))['total'] or 0,
            'total': total_stats['total'] or 0,
            'total_auth': total_stats['auth'] or 0,
            'total_anon': total_stats['anon'] or 0,
            'total_users': user_qs.aggregate(total=Count('user', distinct=True))['total'] or 0,
            'total_visitors': SiteVisitor.objects.count(),
            'total_demo_clicks': total_stats['demo'] or 0,
            'total_demo_visitors': SiteVisitor.objects.filter(demo_click_count__gt=0).count(),
            'graphs_html': self._site_usage_graphs_html(site_qs),
        }

    def _month_start(self, value):
        return value.replace(day=1)

    def _add_months(self, value, months):
        month_index=value.year * 12 + value.month - 1 + months
        return value.replace(year=month_index // 12, month=month_index % 12 + 1, day=1)

    def _chart_html(self, title, subtitle, values, color):
        max_count=max([count for _, count, _ in values], default=0) or 1
        total=sum(count for _, count, _ in values)
        average=round(total / len(values), 1) if values else 0
        latest=values[-1][1] if values else 0
        peak_label, peak_count, _=max(values, key=lambda item: item[1], default=('', 0, ''))
        first_label=values[0][0] if values else ''
        middle_label=values[len(values)//2][0] if values else ''
        last_label=values[-1][0] if values else ''
        width=360
        height=92
        gap=2
        bar_width=max(2, (width - gap * max(len(values) - 1, 0)) / max(len(values), 1))
        bars=[]
        for index, (label, count, detail_text) in enumerate(values):
            bar_height=max(1, (count / max_count) * (height - 6)) if count else 1
            x=index * (bar_width + gap)
            y=height - bar_height
            bars.append(
                f'<rect x="{x:.2f}" y="{y:.2f}" width="{bar_width:.2f}" height="{bar_height:.2f}" rx="1.5" fill="{color}">'
                f'<title>{label}: {count} requests{detail_text}</title>'
                '</rect>'
            )
        return (
            '<div style="border:1px solid var(--hairline-color,#ddd);border-radius:8px;padding:10px;background:var(--body-bg,#fff);min-width:260px">'
            '<div style="display:flex;justify-content:space-between;gap:8px;align-items:start;margin-bottom:8px">'
            f'<div><h3 style="margin:0;font-size:14px">{title}</h3><div style="color:var(--quiet-color,#666);font-size:11px">{subtitle}</div></div>'
            f'<div style="font-size:18px;font-weight:600;line-height:1">{total}</div>'
            '</div>'
            f'<svg viewBox="0 0 {width} {height}" width="100%" height="92" role="img" aria-label="{title}: {total} requests">'
            f'<line x1="0" y1="{height - 1}" x2="{width}" y2="{height - 1}" stroke="var(--hairline-color,#ddd)" />'
            f'{"".join(bars)}'
            '</svg>'
            f'<div style="display:flex;justify-content:space-between;color:var(--quiet-color,#666);font-size:10px;margin-top:2px"><span>{first_label}</span><span>{middle_label}</span><span>{last_label}</span></div>'
            '<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin-top:8px;font-size:11px;color:var(--quiet-color,#666)">'
            f'<div><strong style="color:var(--body-fg,#333)">{latest}</strong><br>latest</div>'
            f'<div><strong style="color:var(--body-fg,#333)">{average}</strong><br>avg/bar</div>'
            f'<div><strong style="color:var(--body-fg,#333)">{peak_count}</strong><br>peak {peak_label}</div>'
            '</div>'
            '</div>'
        )

    def _multi_series_chart_html(self, title, subtitle, values, series):
        max_count=max([metrics.get(key, 0) for _, metrics in values for key, _, _ in series], default=0) or 1
        total=sum(metrics.get('total', 0) for _, metrics in values)
        latest=values[-1][1].get('total', 0) if values else 0
        peak_label, peak_metrics=max(values, key=lambda item: item[1].get('total', 0), default=('', {}))
        peak_count=peak_metrics.get('total', 0)
        first_label=values[0][0] if values else ''
        middle_label=values[len(values)//2][0] if values else ''
        last_label=values[-1][0] if values else ''
        width=440
        height=128
        left_pad=8
        right_pad=8
        top_pad=8
        bottom_pad=14
        plot_width=width - left_pad - right_pad
        plot_height=height - top_pad - bottom_pad

        visual_offsets={
            'authenticated': -4,
            'demo': 0,
            'anonymous': 4,
            'total': 8,
        }

        def point(index, count, key=None):
            if len(values) <= 1:
                x=left_pad + plot_width
            else:
                x=left_pad + (index / (len(values) - 1)) * plot_width
            y=top_pad + plot_height - ((count / max_count) * plot_height if max_count else 0)
            if key:
                y += visual_offsets.get(key, 0)
                y = max(top_pad, min(top_pad + plot_height, y))
            return x, y

        lines=[]
        # Draw total first, then overlapping state flags in the requested visible
        # order: authentication -> demo account -> no authentication. Later SVG
        # lines sit visually above earlier ones.
        draw_order={key: index for index, key in enumerate(('total','authenticated','demo','anonymous'))}
        for key, label, color in sorted(series, key=lambda item: draw_order.get(item[0], 99)):
            points=[point(index, metrics.get(key, 0), key) for index, (_, metrics) in enumerate(values)]
            point_text=' '.join(f'{x:.2f},{y:.2f}' for x, y in points)
            stroke_width='3.2' if key in ('demo','anonymous') else '2.4'
            dash=' stroke-dasharray="5 3"' if key == 'demo' else ''
            opacity='0.82' if key == 'anonymous' else '0.92'
            circles=''.join(
                f'<circle cx="{x:.2f}" cy="{y:.2f}" r="2.8" fill="{color}" stroke="var(--body-bg,#fff)" stroke-width="0.8" opacity="0.98" />'
                for x, y in points
            )
            lines.append(
                f'<polyline points="{point_text}" fill="none" stroke="{color}" stroke-width="{stroke_width}" stroke-linecap="round" stroke-linejoin="round" opacity="{opacity}"{dash} />'
                f'{circles}'
            )

        tooltip_width=plot_width / max(len(values), 1)
        tooltips=[]
        for index, (label, metrics) in enumerate(values):
            x, _=point(index, 0)
            title_text=', '.join(f'{series_label}: {metrics.get(key, 0)}' for key, series_label, _ in series)
            tooltips.append(
                f'<rect x="{max(left_pad, x - tooltip_width / 2):.2f}" y="0" width="{tooltip_width:.2f}" height="{height}" fill="transparent">'
                f'<title>{label}: {title_text}</title>'
                '</rect>'
            )

        y_mid=top_pad + plot_height / 2
        legend=''.join(
            f'<span style="display:inline-flex;align-items:center;gap:4px;margin-right:10px;white-space:nowrap"><span style="width:14px;height:3px;border-radius:2px;background:{color};display:inline-block"></span>{label}</span>'
            for _, label, color in series
        )
        return (
            '<div style="border:1px solid var(--hairline-color,#ddd);border-radius:8px;padding:10px;background:var(--body-bg,#fff);min-width:280px">'
            '<div style="display:flex;justify-content:space-between;gap:8px;align-items:start;margin-bottom:8px">'
            f'<div><h3 style="margin:0;font-size:14px">{title}</h3><div style="color:var(--quiet-color,#666);font-size:11px">{subtitle}</div></div>'
            f'<div style="font-size:18px;font-weight:600;line-height:1" title="Sum of total users across shown points">{total}</div>'
            '</div>'
            f'<div style="font-size:10px;color:var(--quiet-color,#666);margin-bottom:5px">{legend}</div>'
            f'<svg viewBox="0 0 {width} {height}" width="100%" height="128" role="img" aria-label="{title}: overlapping users by category">'
            f'<line x1="{left_pad}" y1="{top_pad}" x2="{left_pad}" y2="{top_pad + plot_height}" stroke="var(--hairline-color,#ddd)" />'
            f'<line x1="{left_pad}" y1="{top_pad + plot_height}" x2="{width - right_pad}" y2="{top_pad + plot_height}" stroke="var(--hairline-color,#ddd)" />'
            f'<line x1="{left_pad}" y1="{y_mid:.2f}" x2="{width - right_pad}" y2="{y_mid:.2f}" stroke="var(--hairline-color,#ddd)" opacity="0.45" />'
            f'{"".join(lines)}'
            f'{"".join(tooltips)}'
            '</svg>'
            f'<div style="display:flex;justify-content:space-between;color:var(--quiet-color,#666);font-size:10px;margin-top:2px"><span>{first_label}</span><span>{middle_label}</span><span>{last_label}</span></div>'
            '<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin-top:8px;font-size:11px;color:var(--quiet-color,#666)">'
            f'<div><strong style="color:var(--body-fg,#333)">{latest}</strong><br>latest total</div>'
            f'<div><strong style="color:var(--body-fg,#333)">{round(total / len(values), 1) if values else 0}</strong><br>avg total/point</div>'
            f'<div><strong style="color:var(--body-fg,#333)">{peak_count}</strong><br>peak {peak_label}</div>'
            '</div>'
            '</div>'
        )

    def _site_usage_graphs_html(self, qs):
        today=timezone.localdate()
        visitor_rows=list(VisitorDailyUsage.objects.values('date','visitor_id','had_anonymous','had_authenticated','demo_click_count'))
        visitor_totals=list(SiteVisitor.objects.values('id','first_seen_at','had_anonymous','had_authenticated','demo_click_count','demo_last_clicked_at'))
        series=(
            ('authenticated', 'Authentication', '#52b788'),
            ('demo', 'Demo account', '#f5a623'),
            ('anonymous', 'No authentication', '#d9534f'),
            ('total', 'Total users', '#417690'),
        )

        def metrics_for_range(start, end):
            matching=[row for row in visitor_rows if start <= row['date'] < end]
            total_visitors={row['visitor_id'] for row in matching}
            anonymous_visitors={row['visitor_id'] for row in matching if row['had_anonymous']}
            authenticated_visitors={row['visitor_id'] for row in matching if row['had_authenticated']}
            demo_visitors={row['visitor_id'] for row in matching if row['demo_click_count'] > 0}
            return {
                'anonymous': len(anonymous_visitors),
                'demo': len(demo_visitors),
                'authenticated': len(authenticated_visitors),
                'total': len(total_visitors),
            }

        def date_from_datetime(value):
            return timezone.localdate(value) if value else None

        def cumulative_metrics(end):
            total_visitors=set()
            anonymous_visitors=set()
            authenticated_visitors=set()
            demo_visitors=set()
            for row in visitor_totals:
                first_seen=date_from_datetime(row['first_seen_at'])
                if first_seen and first_seen < end:
                    total_visitors.add(row['id'])
                    if row['had_anonymous']:
                        anonymous_visitors.add(row['id'])
                    if row['had_authenticated']:
                        authenticated_visitors.add(row['id'])
                demo_seen=date_from_datetime(row['demo_last_clicked_at'])
                if row['demo_click_count'] > 0 and ((demo_seen and demo_seen < end) or (not demo_seen and first_seen and first_seen < end)):
                    demo_visitors.add(row['id'])
            return {
                'anonymous': len(anonymous_visitors),
                'demo': len(demo_visitors),
                'authenticated': len(authenticated_visitors),
                'total': len(total_visitors),
            }

        daily_start=today - timedelta(days=29)
        daily=[]
        for offset in range(30):
            day=daily_start + timedelta(days=offset)
            daily.append((day.isoformat(), metrics_for_range(day, day + timedelta(days=1))))

        weekly_start=today - timedelta(days=83)
        weekly=[]
        for offset in range(12):
            start=weekly_start + timedelta(days=offset * 7)
            end=start + timedelta(days=7)
            weekly.append((f'{start.strftime("%m-%d")}–{(end - timedelta(days=1)).strftime("%m-%d")}', metrics_for_range(start, end)))

        month_start=self._add_months(self._month_start(today), -11)
        monthly=[]
        for offset in range(12):
            start=self._add_months(month_start, offset)
            end=self._add_months(start, 1)
            monthly.append((start.strftime('%Y-%m'), metrics_for_range(start, end)))

        first_seen_dates=[date_from_datetime(row['first_seen_at']) for row in visitor_totals if row['first_seen_at']]
        first_date=min(first_seen_dates, default=month_start)
        total_start=self._month_start(first_date)
        month_count=(today.year - total_start.year) * 12 + today.month - total_start.month + 1
        if month_count > 24:
            visible_start=self._add_months(self._month_start(today), -23)
            month_count=24
        else:
            visible_start=total_start
        total=[]
        for offset in range(month_count):
            start=self._add_months(visible_start, offset)
            end=self._add_months(start, 1)
            total.append((start.strftime('%Y-%m'), cumulative_metrics(end)))

        html=(
            '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:10px;min-width:600px">'
            + self._multi_series_chart_html('Daily usage', 'Unique users per day, last 30 days', daily, series)
            + self._multi_series_chart_html('Weekly usage', 'Unique users per 7-day week, last 12 weeks', weekly, series)
            + self._multi_series_chart_html('Monthly usage', 'Unique users per calendar month, last 12 months', monthly, series)
            + self._multi_series_chart_html('Total usage', 'Cumulative unique users by month, all time shown up to 24 months', total, series)
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
            '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:10px;min-width:600px">'
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

@admin.register(ScheduledTaskRun)
class ScheduledTaskRunAdmin(admin.ModelAdmin):
    list_display=('name','last_run_at','updated_at')
    search_fields=('name',)
    readonly_fields=('updated_at',)

@admin.register(SiteDailyUsage)
class SiteDailyUsageAdmin(admin.ModelAdmin):
    list_display=('date','request_count','authenticated_count','anonymous_count','unique_visitor_count','demo_click_count','demo_unique_visitor_count','last_seen_at')
    list_filter=('date',)
    date_hierarchy='date'
    readonly_fields=('created_at','updated_at')

@admin.register(SiteVisitor)
class SiteVisitorAdmin(admin.ModelAdmin):
    list_display=('visitor_id','user','had_anonymous','had_authenticated','first_seen_at','last_seen_at','request_count','demo_click_count','demo_last_clicked_at')
    search_fields=('visitor_id','user__username','user__email')
    list_filter=('first_seen_at','last_seen_at','demo_last_clicked_at')
    date_hierarchy='last_seen_at'
    readonly_fields=('created_at','updated_at')

@admin.register(UserDailyUsage)
class UserDailyUsageAdmin(admin.ModelAdmin):
    list_display=('user','date','request_count','last_seen_at')
    search_fields=('user__username','user__email')
    list_filter=('date',)
    date_hierarchy='date'
    readonly_fields=('created_at','updated_at')

@admin.register(VisitorDailyUsage)
class VisitorDailyUsageAdmin(admin.ModelAdmin):
    list_display=('visitor','date','request_count','had_anonymous','had_authenticated','demo_click_count','last_seen_at','demo_last_clicked_at')
    search_fields=('visitor__visitor_id','visitor__user__username','visitor__user__email')
    list_filter=('date',)
    date_hierarchy='date'
    readonly_fields=('created_at','updated_at')

@admin.register(InviteCode)
class InviteCodeAdmin(admin.ModelAdmin):
    list_display=('code','label','active','expires_at','created_at')
    search_fields=('code','label')
    list_filter=('active','created_at')
