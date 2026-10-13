import logging
from threading import Thread

from django.conf import settings
from django.db import connection
from django.db.models import F
from django.utils import timezone

from .models import SiteDailyUsage, SiteVisitor, UserDailyUsage, VisitorDailyUsage
from .services.analytics import VISITOR_COOKIE_MAX_AGE, VISITOR_COOKIE_NAME, clean_visitor_id, new_visitor_id
from .services.demo_data import DEMO_USERNAME

logger = logging.getLogger(__name__)


class UserUsageMiddleware:
    """Aggregate lightweight site and per-user usage counts for the admin dashboard."""

    IGNORED_PREFIXES = ('/static/', '/favicon', '/robots.txt', '/api/health/')

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = getattr(request, 'path_info', '') or ''
        track_visitor = not self.is_ignored_path(path)
        set_visitor_cookie = False
        if track_visitor:
            visitor_id = clean_visitor_id(request.COOKIES.get(VISITOR_COOKIE_NAME, ''))
            if not visitor_id:
                visitor_id = new_visitor_id()
                set_visitor_cookie = True
            request.dachapply_visitor_id = visitor_id

        response = self.get_response(request)
        if track_visitor:
            self.record_usage(request)
            if set_visitor_cookie:
                response.set_cookie(
                    VISITOR_COOKIE_NAME,
                    request.dachapply_visitor_id,
                    max_age=VISITOR_COOKIE_MAX_AGE,
                    httponly=True,
                    samesite='Lax',
                    secure=request.is_secure(),
                )
        return response

    def is_ignored_path(self, path):
        return any(path.startswith(prefix) for prefix in self.IGNORED_PREFIXES)

    def record_usage(self, request):
        path = getattr(request, 'path_info', '') or ''
        if self.is_ignored_path(path):
            return

        # Everything the recorder needs is read here, on the request thread, as plain values: the
        # request and its lazy user must never cross to another thread, and localdate() depends on
        # the timezone activated for this request.
        now = timezone.now()
        date = timezone.localdate(now)
        user = getattr(request, 'user', None)
        is_authenticated = bool(getattr(user, 'is_authenticated', False))
        is_demo_user = is_authenticated and getattr(user, 'get_username', lambda: '')().lower() == DEMO_USERNAME.lower()
        real_user_id = user.pk if is_authenticated and not is_demo_user else None
        visitor_id = clean_visitor_id(getattr(request, 'dachapply_visitor_id', ''))

        # TASK-281: against remote Neon these ~8-10 round trips cost ~400 ms per request, so with
        # USAGE_RECORD_ASYNC (on when the DB pool is) they run after the response, off the request.
        if settings.USAGE_RECORD_ASYNC:
            Thread(target=self.record_usage_in_background, args=(now, date, visitor_id, real_user_id), daemon=True).start()
        else:
            self.record_usage_values(now, date, visitor_id, real_user_id)

    def record_usage_in_background(self, now, date, visitor_id, real_user_id):
        """Thread target: a lost usage count must never surface anywhere, and the thread's connection
        goes back to the pool (or is closed) when it is done."""
        try:
            self.record_usage_values(now, date, visitor_id, real_user_id)
        except Exception:
            logger.debug('Recording usage failed.', exc_info=True)
        finally:
            connection.close()

    def record_usage_values(self, now, date, visitor_id, real_user_id):
        is_real_authenticated = real_user_id is not None

        site_usage, _ = SiteDailyUsage.objects.get_or_create(
            date=date,
            defaults={'request_count': 0, 'last_seen_at': now},
        )
        if visitor_id:
            visitor, _ = SiteVisitor.objects.get_or_create(
                visitor_id=visitor_id,
                defaults={'last_seen_at': now},
            )
            visitor_updates = {
                'request_count': F('request_count') + 1,
                'last_seen_at': now,
                'had_authenticated' if is_real_authenticated else 'had_anonymous': True,
            }
            if is_real_authenticated:
                visitor_updates['user_id'] = real_user_id
            SiteVisitor.objects.filter(pk=visitor.pk).update(**visitor_updates)
            daily_visitor, daily_visitor_created = VisitorDailyUsage.objects.get_or_create(
                visitor=visitor,
                date=date,
                defaults={'request_count': 0, 'last_seen_at': now},
            )
            daily_visitor_updates = {
                'request_count': F('request_count') + 1,
                'last_seen_at': now,
                'had_authenticated' if is_real_authenticated else 'had_anonymous': True,
            }
            VisitorDailyUsage.objects.filter(pk=daily_visitor.pk).update(**daily_visitor_updates)
        else:
            daily_visitor_created = False

        site_updates = {
            'request_count': F('request_count') + 1,
            'last_seen_at': now,
        }
        if daily_visitor_created:
            site_updates['unique_visitor_count'] = F('unique_visitor_count') + 1
        if is_real_authenticated:
            site_updates['authenticated_count'] = F('authenticated_count') + 1
        else:
            site_updates['anonymous_count'] = F('anonymous_count') + 1
        SiteDailyUsage.objects.filter(pk=site_usage.pk).update(**site_updates)

        if not is_real_authenticated:
            return

        usage, _ = UserDailyUsage.objects.get_or_create(
            user_id=real_user_id,
            date=date,
            defaults={'request_count': 0, 'last_seen_at': now},
        )
        UserDailyUsage.objects.filter(pk=usage.pk).update(
            request_count=F('request_count') + 1,
            last_seen_at=now,
        )
