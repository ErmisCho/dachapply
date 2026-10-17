import logging
from concurrent.futures import ThreadPoolExecutor

from django.conf import settings
from django.db import connection
from django.db.models import F
from django.utils import timezone

from .models import SiteDailyUsage, SiteVisitor, UserDailyUsage, VisitorDailyUsage
from .services.analytics import VISITOR_COOKIE_MAX_AGE, VISITOR_COOKIE_NAME, clean_visitor_id, new_visitor_id
from .services.demo_data import DEMO_USERNAME

logger = logging.getLogger(__name__)

# 2026-10-17: one Thread per request let usage writes pile up whenever Neon was slow (a local device
# polls / every 2 s), taking all 8 pool connections ("couldn't get a connection after 10.00 sec").
# One worker means usage recording holds at most one connection; a backlog only delays counters.
_usage_writer = ThreadPoolExecutor(max_workers=1, thread_name_prefix='usage-record')


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
            _usage_writer.submit(self.record_usage_in_background, now, date, visitor_id, real_user_id)
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

    @staticmethod
    def bump(rows, updates, get_or_create):
        """F()-increment the counter row in `rows`, creating it first only when the UPDATE matched
        nothing; returns whether it was created. TASK-282: get_or_create-then-update was two round
        trips per counter on every request, and all but the first request of a day/visitor find the
        row, so they now pay one. A lost create race still lands on get_or_create's get, and the
        increment is still the same single F() UPDATE."""
        if rows.update(**updates):
            return False
        row, created = get_or_create()
        type(row).objects.filter(pk=row.pk).update(**updates)
        return created

    def record_usage_values(self, now, date, visitor_id, real_user_id):
        is_real_authenticated = real_user_id is not None
        counter_defaults = {'request_count': 0, 'last_seen_at': now}

        if visitor_id:
            visitor_updates = {
                'request_count': F('request_count') + 1,
                'last_seen_at': now,
                'had_authenticated' if is_real_authenticated else 'had_anonymous': True,
            }
            if is_real_authenticated:
                visitor_updates['user_id'] = real_user_id
            self.bump(SiteVisitor.objects.filter(visitor_id=visitor_id), visitor_updates,
                      lambda: SiteVisitor.objects.get_or_create(visitor_id=visitor_id, defaults={'last_seen_at': now}))
            daily_visitor_updates = {
                'request_count': F('request_count') + 1,
                'last_seen_at': now,
                'had_authenticated' if is_real_authenticated else 'had_anonymous': True,
            }
            daily_visitor_created = self.bump(
                VisitorDailyUsage.objects.filter(visitor__visitor_id=visitor_id, date=date), daily_visitor_updates,
                lambda: VisitorDailyUsage.objects.get_or_create(visitor=SiteVisitor.objects.get(visitor_id=visitor_id), date=date, defaults=counter_defaults))
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
        self.bump(SiteDailyUsage.objects.filter(date=date), site_updates,
                  lambda: SiteDailyUsage.objects.get_or_create(date=date, defaults=counter_defaults))

        if not is_real_authenticated:
            return

        self.bump(UserDailyUsage.objects.filter(user_id=real_user_id, date=date),
                  {'request_count': F('request_count') + 1, 'last_seen_at': now},
                  lambda: UserDailyUsage.objects.get_or_create(user_id=real_user_id, date=date, defaults=counter_defaults))
