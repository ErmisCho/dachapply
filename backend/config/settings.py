import os
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in ('1', 'true', 'yes', 'on')


def env_list(name, default=''):
    return [item.strip() for item in os.getenv(name, default).split(',') if item.strip()]


DEBUG = env_bool('DEBUG', True)

SECRET_KEY = os.getenv('SECRET_KEY')
if DEBUG:
    SECRET_KEY = SECRET_KEY or 'dev-only-change-me'
elif not SECRET_KEY or SECRET_KEY == 'dev-only-change-me':
    raise ImproperlyConfigured('SECRET_KEY must be set to a strong unique value when DEBUG=False.')

if DEBUG:
    ALLOWED_HOSTS = env_list('ALLOWED_HOSTS', 'localhost,127.0.0.1,testserver')
    CSRF_TRUSTED_ORIGINS = env_list('CSRF_TRUSTED_ORIGINS', 'http://localhost:5173,http://127.0.0.1:5173,http://localhost:8000,http://127.0.0.1:8000')
    CORS_ALLOWED_ORIGINS = env_list('CORS_ALLOWED_ORIGINS', 'http://localhost:5173,http://127.0.0.1:5173')
else:
    ALLOWED_HOSTS = env_list('ALLOWED_HOSTS')
    if not ALLOWED_HOSTS:
        raise ImproperlyConfigured('ALLOWED_HOSTS must be set when DEBUG=False.')
    CSRF_TRUSTED_ORIGINS = env_list('CSRF_TRUSTED_ORIGINS')
    if not CSRF_TRUSTED_ORIGINS:
        raise ImproperlyConfigured('CSRF_TRUSTED_ORIGINS must be set when DEBUG=False.')
    CORS_ALLOWED_ORIGINS = env_list('CORS_ALLOWED_ORIGINS')

INSTALLED_APPS = [
 'django.contrib.admin','django.contrib.auth','django.contrib.contenttypes','django.contrib.sessions','django.contrib.messages','django.contrib.staticfiles',
 'rest_framework','corsheaders','jobradar'
]
MIDDLEWARE = [
 'django.middleware.security.SecurityMiddleware','whitenoise.middleware.WhiteNoiseMiddleware','corsheaders.middleware.CorsMiddleware',
 'django.middleware.common.CommonMiddleware','config.middleware.NoCacheHtmlMiddleware','django.middleware.csrf.CsrfViewMiddleware','config.middleware.SplitAdminSessionMiddleware','django.contrib.auth.middleware.AuthenticationMiddleware',
 'django.contrib.messages.middleware.MessageMiddleware','django.middleware.clickjacking.XFrameOptionsMiddleware'
]
ROOT_URLCONF='config.urls'
TEMPLATES=[{'BACKEND':'django.template.backends.django.DjangoTemplates','DIRS':[BASE_DIR/'templates', BASE_DIR.parent/'frontend'/'dist'],'APP_DIRS':True,'OPTIONS':{'context_processors':['django.template.context_processors.request','django.contrib.auth.context_processors.auth','django.contrib.messages.context_processors.messages']}}]
WSGI_APPLICATION='config.wsgi.application'

DATABASE_URL = os.getenv('DATABASE_URL')
if DATABASE_URL:
    try:
        import dj_database_url
    except ImportError as exc:
        raise ImproperlyConfigured('DATABASE_URL requires dj-database-url to be installed.') from exc
    DATABASES = {
        'default': dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=int(os.getenv('DB_CONN_MAX_AGE', '600')),
            ssl_require=env_bool('DB_SSL_REQUIRE', not DEBUG),
        )
    }
else:
    if not DEBUG:
        raise ImproperlyConfigured('DATABASE_URL must be set for production when DEBUG=False.')
    DATABASES={'default': {'ENGINE': os.getenv('DB_ENGINE','django.db.backends.sqlite3'), 'NAME': os.getenv('DB_NAME', str(BASE_DIR/'db.sqlite3'))}}

AUTH_PASSWORD_VALIDATORS=[{'NAME':'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},{'NAME':'django.contrib.auth.password_validation.MinimumLengthValidator'},{'NAME':'django.contrib.auth.password_validation.CommonPasswordValidator'},{'NAME':'django.contrib.auth.password_validation.NumericPasswordValidator'}]
LANGUAGE_CODE='en-us'; TIME_ZONE='Europe/Vienna'; USE_I18N=True; USE_TZ=True
STATIC_URL='/static/'; STATIC_ROOT=BASE_DIR/'staticfiles'; STATICFILES_DIRS=[]
STATICFILES_STORAGE='whitenoise.storage.CompressedManifestStaticFilesStorage'
FRONTEND_DIST=BASE_DIR.parent/'frontend'/'dist'
if FRONTEND_DIST.exists(): STATICFILES_DIRS.append(FRONTEND_DIST)
DEFAULT_AUTO_FIELD='django.db.models.BigAutoField'
REST_FRAMEWORK={'DEFAULT_AUTHENTICATION_CLASSES':['rest_framework.authentication.SessionAuthentication'], 'DEFAULT_PERMISSION_CLASSES':['rest_framework.permissions.IsAuthenticated']}
CORS_ALLOW_CREDENTIALS=True
LOGIN_URL='/login'

FRONTEND_URL=os.getenv('FRONTEND_URL', 'http://localhost:5173' if DEBUG else '')
if not DEBUG and not FRONTEND_URL:
    raise ImproperlyConfigured('FRONTEND_URL must be set when DEBUG=False.')

DEFAULT_FROM_EMAIL=os.getenv('DEFAULT_FROM_EMAIL', 'noreply@localhost' if DEBUG else '')
EMAIL_BACKEND=os.getenv('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend' if DEBUG else 'django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST=os.getenv('EMAIL_HOST', 'localhost' if DEBUG else '')
EMAIL_USE_TLS=env_bool('EMAIL_USE_TLS', not DEBUG)
EMAIL_USE_SSL=env_bool('EMAIL_USE_SSL', False)
EMAIL_PORT=int(os.getenv('EMAIL_PORT', '587' if EMAIL_USE_TLS else '25'))
EMAIL_HOST_USER=os.getenv('EMAIL_HOST_USER','')
EMAIL_HOST_PASSWORD=os.getenv('EMAIL_HOST_PASSWORD','')
if not DEBUG and EMAIL_BACKEND.endswith('smtp.EmailBackend'):
    missing = [name for name, value in [('DEFAULT_FROM_EMAIL', DEFAULT_FROM_EMAIL), ('EMAIL_HOST', EMAIL_HOST)] if not value]
    if missing:
        raise ImproperlyConfigured(', '.join(missing) + ' must be set for SMTP email when DEBUG=False.')

SESSION_COOKIE_SECURE=env_bool('SESSION_COOKIE_SECURE', not DEBUG)
CSRF_COOKIE_SECURE=env_bool('CSRF_COOKIE_SECURE', not DEBUG)
SESSION_COOKIE_HTTPONLY=True
SESSION_COOKIE_SAMESITE=os.getenv('SESSION_COOKIE_SAMESITE', 'Lax')
CSRF_COOKIE_SAMESITE=os.getenv('CSRF_COOKIE_SAMESITE', 'Lax')
SECURE_SSL_REDIRECT=env_bool('SECURE_SSL_REDIRECT', not DEBUG)
if env_bool('USE_X_FORWARDED_PROTO', not DEBUG):
    SECURE_PROXY_SSL_HEADER=('HTTP_X_FORWARDED_PROTO','https')
SECURE_HSTS_SECONDS=int(os.getenv('SECURE_HSTS_SECONDS', '0'))
SECURE_HSTS_INCLUDE_SUBDOMAINS=env_bool('SECURE_HSTS_INCLUDE_SUBDOMAINS', False)
SECURE_HSTS_PRELOAD=env_bool('SECURE_HSTS_PRELOAD', False)
SECURE_CONTENT_TYPE_NOSNIFF=True
SECURE_REFERRER_POLICY=os.getenv('SECURE_REFERRER_POLICY', 'same-origin')
