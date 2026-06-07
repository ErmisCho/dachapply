from django.db.models import F
from django.utils import timezone

from .models import SiteDailyUsage, UserDailyUsage


class UserUsageMiddleware:
    """Aggregate lightweight site and per-user usage counts for the admin dashboard."""

    IGNORED_PREFIXES = ('/static/', '/favicon', '/robots.txt')

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        self.record_usage(request)
        return response

    def record_usage(self, request):
        path = getattr(request, 'path_info', '') or ''
        if any(path.startswith(prefix) for prefix in self.IGNORED_PREFIXES):
            return

        now = timezone.now()
        date = timezone.localdate(now)
        user = getattr(request, 'user', None)
        is_authenticated = bool(getattr(user, 'is_authenticated', False))

        site_usage, _ = SiteDailyUsage.objects.get_or_create(
            date=date,
            defaults={'request_count': 0, 'last_seen_at': now},
        )
        site_updates = {
            'request_count': F('request_count') + 1,
            'last_seen_at': now,
        }
        if is_authenticated:
            site_updates['authenticated_count'] = F('authenticated_count') + 1
        else:
            site_updates['anonymous_count'] = F('anonymous_count') + 1
        SiteDailyUsage.objects.filter(pk=site_usage.pk).update(**site_updates)

        if not is_authenticated:
            return

        usage, _ = UserDailyUsage.objects.get_or_create(
            user=user,
            date=date,
            defaults={'request_count': 0, 'last_seen_at': now},
        )
        UserDailyUsage.objects.filter(pk=usage.pk).update(
            request_count=F('request_count') + 1,
            last_seen_at=now,
        )
