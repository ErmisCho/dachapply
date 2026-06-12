from uuid import uuid4

from django.db.models import F
from django.utils import timezone

from jobradar.models import SiteDailyUsage, SiteVisitor, VisitorDailyUsage

VISITOR_COOKIE_NAME = 'dachapply_visitor_id'
VISITOR_COOKIE_MAX_AGE = 60 * 60 * 24 * 400


def clean_visitor_id(value):
    value = (value or '').strip()
    if not value or len(value) > 64:
        return ''
    if not all(ch.isalnum() or ch in ('-', '_') for ch in value):
        return ''
    return value


def new_visitor_id():
    return uuid4().hex


def get_request_visitor_id(request):
    return clean_visitor_id(getattr(request, 'dachapply_visitor_id', '') or request.COOKIES.get(VISITOR_COOKIE_NAME, ''))


def record_demo_click(request):
    """Record a user-controlled demo-login click for visitor analytics in Django admin."""
    visitor_id = get_request_visitor_id(request)
    if not visitor_id:
        return

    now = timezone.now()
    date = timezone.localdate(now)
    visitor, _ = SiteVisitor.objects.get_or_create(
        visitor_id=visitor_id,
        defaults={'last_seen_at': now},
    )
    SiteVisitor.objects.filter(pk=visitor.pk).update(
        had_anonymous=True,
        demo_click_count=F('demo_click_count') + 1,
        demo_last_clicked_at=now,
        last_seen_at=now,
    )

    daily, daily_created = VisitorDailyUsage.objects.get_or_create(
        visitor=visitor,
        date=date,
        defaults={'request_count': 0, 'demo_click_count': 0, 'last_seen_at': now},
    )
    first_demo_click_today = daily.demo_click_count == 0
    VisitorDailyUsage.objects.filter(pk=daily.pk).update(
        had_anonymous=True,
        demo_click_count=F('demo_click_count') + 1,
        demo_last_clicked_at=now,
        last_seen_at=now,
    )

    site_usage, _ = SiteDailyUsage.objects.get_or_create(
        date=date,
        defaults={'request_count': 0, 'last_seen_at': now},
    )
    updates = {
        'demo_click_count': F('demo_click_count') + 1,
        'last_seen_at': now,
    }
    if daily_created:
        updates['unique_visitor_count'] = F('unique_visitor_count') + 1
    if first_demo_click_today:
        updates['demo_unique_visitor_count'] = F('demo_unique_visitor_count') + 1
    SiteDailyUsage.objects.filter(pk=site_usage.pk).update(**updates)
