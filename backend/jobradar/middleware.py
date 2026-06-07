from django.db.models import F
from django.utils import timezone

from .models import UserDailyUsage


class UserUsageMiddleware:
    """Aggregate lightweight per-user usage counts for the admin dashboard."""

    IGNORED_PREFIXES = ('/static/', '/favicon', '/robots.txt')

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        self.record_usage(request)
        return response

    def record_usage(self, request):
        user = getattr(request, 'user', None)
        if not getattr(user, 'is_authenticated', False):
            return
        path = getattr(request, 'path_info', '') or ''
        if any(path.startswith(prefix) for prefix in self.IGNORED_PREFIXES):
            return

        now = timezone.now()
        usage, _ = UserDailyUsage.objects.get_or_create(
            user=user,
            date=timezone.localdate(now),
            defaults={'request_count': 0, 'last_seen_at': now},
        )
        UserDailyUsage.objects.filter(pk=usage.pk).update(
            request_count=F('request_count') + 1,
            last_seen_at=now,
        )
