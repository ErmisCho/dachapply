import hashlib

from rest_framework.exceptions import Throttled
from rest_framework.settings import api_settings
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import exception_handler


class ConfiguredRateThrottle(SimpleRateThrottle):
    def get_rate(self):
        return api_settings.DEFAULT_THROTTLE_RATES.get(self.scope)


class IPThrottle(ConfiguredRateThrottle):
    """Simple cache-backed throttle keyed by client IP address."""

    scope = None

    def get_cache_key(self, request, view):
        if not self.scope:
            return None
        return self.cache_format % {'scope': self.scope, 'ident': self.get_ident(request)}


class LoginIPThrottle(IPThrottle):
    scope = 'login_ip'


class RegisterIPThrottle(IPThrottle):
    scope = 'register_ip'


class PasswordResetIPThrottle(IPThrottle):
    scope = 'password_reset_ip'


class PublicSubmitIPThrottle(IPThrottle):
    scope = 'public_submit_ip'


class LoginAccountThrottle(ConfiguredRateThrottle):
    """Throttle repeated login attempts for the same username/email."""

    scope = 'login_account'

    def get_cache_key(self, request, view):
        username = (request.data.get('username') or request.data.get('email') or '').strip().lower()
        if not username:
            return None
        ident = hashlib.sha256(username.encode('utf-8')).hexdigest()
        return self.cache_format % {'scope': self.scope, 'ident': ident}


class PasswordResetEmailThrottle(ConfiguredRateThrottle):
    """Throttle repeated password reset emails for the same address."""

    scope = 'password_reset_email'

    def get_cache_key(self, request, view):
        email = (request.data.get('email') or '').strip().lower()
        if not email:
            return None
        ident = hashlib.sha256(email.encode('utf-8')).hexdigest()
        return self.cache_format % {'scope': self.scope, 'ident': ident}


class ImportUserThrottle(ConfiguredRateThrottle):
    """Throttle expensive authenticated import endpoints per user."""

    scope = 'import_user'

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            ident = f'user:{request.user.pk}'
        else:
            ident = self.get_ident(request)
        return self.cache_format % {'scope': self.scope, 'ident': ident}


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if isinstance(exc, Throttled) and response is not None:
        response.data = {
            'detail': 'Rate limit exceeded. Try again later.',
            'available_in_seconds': exc.wait,
        }
    return response
