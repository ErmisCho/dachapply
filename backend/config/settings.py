import os
import sys
import time
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

# TASK-100: snapshot the environment exactly as the process received it, before this module (or its
# own load_env_file calls below) ever writes to os.environ.
#
# Why a snapshot and not a plain "is this key already in os.environ" check: Django's lazy settings
# retries importing this module on every failed attribute access (LazySettings._setup() is called
# again from LazyObject.__getattr__ as long as self._wrapped stays unset), and CPython drops a module
# that raised an exception from sys.modules, so a raise here means config.settings re-executes from
# scratch. os.environ is a real process-global, though, and is NOT rolled back between those
# attempts -- so a key load_env_file() set on a first (failed, e.g. guard-raised) pass would look
# "already in the environment" on the retry, and the guard below would then wave it through as if a
# human had typed it. Measured: without this snapshot, `manage.py check` against a production-shaped
# root .env raises once, gets silently swallowed by Django's own settings.INSTALLED_APPS probe, and
# the retry it triggers loads DATABASE_URL from the .env file completely unguarded.
#
# The marker survives retries for the same reason the bug exists: once written, later passes see it
# already there and never overwrite it, so _process_env_keys reflects the one true "before this
# module touched anything" snapshot on every attempt, not just the first.
_ENV_SNAPSHOT_MARKER = '_DACHAPPLY_PROCESS_ENV_KEYS'
if _ENV_SNAPSHOT_MARKER not in os.environ:
    os.environ[_ENV_SNAPSHOT_MARKER] = '\n'.join(os.environ.keys())
_process_env_keys = frozenset(os.environ[_ENV_SNAPSHOT_MARKER].split('\n'))


def load_env_file(path):
    """Load KEY=VALUE lines from `path` into os.environ, without overriding anything already set.

    Returns the set of keys this call actually populated that were not in the process environment
    to begin with (per _process_env_keys, not per the live, mutable os.environ -- see above).
    TASK-100 uses this to tell "this value came from a persisted .env file" apart from "this value
    came from the real process environment" -- the container and CI never ship a .env file (see
    _env_file_keys below), so only a local run can trip that distinction.
    """
    if not path.exists():
        return set()
    set_keys = set()
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key not in _process_env_keys:
            set_keys.add(key)
        os.environ.setdefault(key, value)
    return set_keys


_env_file_keys = load_env_file(BASE_DIR.parent / '.env')
_env_file_keys |= load_env_file(BASE_DIR / '.env')


# TASK-111 (owner decision 2026-08-16): commands that SERVE the app locally use the same remote
# database as the deployed site, so the local app and the website always show the same data.
# Everything else (migrate, flush, dbshell, shell, loaddata, ...) keeps TASK-100's guard: reaching
# production from a laptop stays an explicit per-command opt-in. check_mailbox is a server in this
# sense -- its whole purpose is writing suggestions where the website can show them.
LOCAL_PROD_DB_SERVING_COMMANDS = frozenset({'runserver', 'check_mailbox'})
# Separate reason, deliberately not folded into the set above: these commands open no database
# connection at all, so the guard has nothing to protect and refusing to start is a false positive
# that blocks real work. gmail_oauth_setup does an OAuth handshake and writes a token file; it
# imports settings only because it is a management command. Keeping the two sets apart matters --
# "exempt because it deliberately uses production" and "exempt because it never touches a database"
# are different claims, and merging them would let a future DB-touching command inherit the wrong one.
LOCAL_DB_GUARD_NO_DB_COMMANDS = frozenset({'gmail_oauth_setup'})


def local_db_guard_blocks(database_url, file_sourced_keys, allow_prod_db, argv=None):
    """True if a DATABASE_URL should be refused rather than used. See TASK-100 and TASK-111.

    Blocks only a value that came from a persisted .env file (`database_url` truthy and
    'DATABASE_URL' present in `file_sourced_keys`) with no opt-in. A value the operator typed for
    this command -- exported in the shell, or the DATABASE_URL='' + DB_NAME=... workaround, which
    leaves 'DATABASE_URL' out of file_sourced_keys entirely -- is left alone. Serving commands
    (LOCAL_PROD_DB_SERVING_COMMANDS) are never blocked: per TASK-111 the local app deliberately
    runs against the same remote database as the deployed site. Commands that open no database
    connection at all (LOCAL_DB_GUARD_NO_DB_COMMANDS) are also never blocked, for the opposite
    reason -- there is nothing to protect, so refusing to start is a false positive.
    """
    args = sys.argv if argv is None else argv
    command = args[1] if len(args) > 1 else ''
    if command in LOCAL_PROD_DB_SERVING_COMMANDS or command in LOCAL_DB_GUARD_NO_DB_COMMANDS:
        return False
    return bool(database_url) and 'DATABASE_URL' in file_sourced_keys and not allow_prod_db


def env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in ('1', 'true', 'yes', 'on')


def env_list(name, default=''):
    return [item.strip() for item in os.getenv(name, default).split(',') if item.strip()]


def normalize_smtp_password(host, password):
    """Normalize provider-specific SMTP password formats.

    Google displays Gmail App Passwords in four groups separated by spaces,
    but SMTP AUTH expects the compact 16-character token.
    """
    password = password or ''
    compact_password = ''.join(password.split())
    if (
        (host or '').strip().lower() == 'smtp.gmail.com'
        and compact_password != password
        and len(compact_password) == 16
        and compact_password.isalnum()
    ):
        return compact_password
    return password


DEBUG = env_bool('DEBUG', True)
DACHAPPLY_ENV = os.getenv('DACHAPPLY_ENV', 'local' if DEBUG else 'production')
CODEX_CV_ENABLED = env_bool('CODEX_CV_ENABLED', DEBUG)
CODEX_CV_OWNER_EMAIL = os.getenv('CODEX_CV_OWNER_EMAIL', 'ermis.chorinopoulos@gmail.com')
# Where the in-app feedback link points. Any URL works (a form, an issue tracker); it defaults to a
# mailto for the owner so the link is never dead. A mailto opens the user's own mail client with an
# empty body, so nothing about their jobs is transmitted unless they type it themselves.
FEEDBACK_URL = os.getenv('FEEDBACK_URL') or (f'mailto:{CODEX_CV_OWNER_EMAIL}?subject=DACHApply%20feedback' if CODEX_CV_OWNER_EMAIL else '')
CODEX_CV_WORKSPACE = os.getenv('CODEX_CV_WORKSPACE', r'C:\latex' if DEBUG else '')
CODEX_CV_CACHE = env_bool('CODEX_CV_CACHE', True)
CODEX_CANDIDATE_EVIDENCE_PATH = os.getenv('CODEX_CANDIDATE_EVIDENCE_PATH', str(BASE_DIR.parent/'Ermis-Chorinopoulos-Candidate-Evidence.md') if DEBUG else '')
CODEX_APPLICATION_RULES_PATH = os.getenv('CODEX_APPLICATION_RULES_PATH', str(BASE_DIR.parent/'job-application-adaptation-rules.md'))
CODEX_CV_OPEN_OUTPUT_FOLDER = env_bool('CODEX_CV_OPEN_OUTPUT_FOLDER', DEBUG)

# TASK-109: local-only Gmail mailbox check. Same idiom as CODEX_CV_* above -- read only from
# env/.env (which never ships to Azure or this repo), no credential default, and every consumer
# treats an unset GMAIL_IMAP_USER/APP_PASSWORD as "not configured" rather than raising, so the
# feature is simply absent everywhere except the owner's own machine. Gmail app passwords are shown
# in four space-separated groups; IMAP AUTH wants the compact form, same fix as
# normalize_smtp_password above but unconditional since this var is Gmail-only by name.
GMAIL_IMAP_HOST = os.getenv('GMAIL_IMAP_HOST', 'imap.gmail.com')
GMAIL_IMAP_USER = os.getenv('GMAIL_IMAP_USER', '')
GMAIL_IMAP_APP_PASSWORD = ''.join((os.getenv('GMAIL_IMAP_APP_PASSWORD') or '').split())
# TASK-110: IMAP name of the Drafts special-use mailbox that reply drafts get APPENDed to. Correct
# for an English-locale Gmail account; a differently-localized account names it differently, hence
# the override instead of a hardcoded constant in services/mailbox.py.
GMAIL_DRAFTS_FOLDER = os.getenv('GMAIL_DRAFTS_FOLDER', '[Gmail]/Drafts')
# TASK-110 AC2: guardrail config for reply drafting. Both are also editable per account in
# Settings -> Mailbox check (local mode) (UserProfile.mailbox_salary_floor_eur/mailbox_do_not_disclose);
# when set here, the env value wins over that profile value -- an operator-set floor/blocklist on the
# machine actually running check_mailbox can never be relaxed through the website alone. Left unset,
# neither guardrail restricts anything (falls through to whatever the profile has, itself defaulting
# to "no floor, no blocklist"), same opt-in shape as every other unset-means-absent var in this block.
MAILBOX_SALARY_FLOOR_EUR = os.getenv('MAILBOX_SALARY_FLOOR_EUR', '').strip()
MAILBOX_DO_NOT_DISCLOSE = env_list('MAILBOX_DO_NOT_DISCLOSE', '')

# TASK-109 AC1: Gmail-API OAuth path -- the remaining route when the owner has declined 2-Step
# Verification (Google only issues app passwords with 2SV on, and retired "less secure app access"
# entirely, so GMAIL_IMAP_APP_PASSWORD above is then simply unusable). Same "absent unless
# configured" idiom as GMAIL_IMAP_USER/APP_PASSWORD: unset client id/secret means run_check() treats
# OAuth as not configured either (see services/mailbox.py run_check()'s gate). Set up once with
# `manage.py gmail_oauth_setup` (see docs/email-setup.md) -- that command writes the refresh token to
# GMAIL_OAUTH_TOKEN_PATH, never here; the client id/secret are the only OAuth values that belong in
# .env, same treatment as every other credential in this block.
# TASK-116: this one OAuth client now also carries calendar.readonly (see
# services.mailbox.GMAIL_OAUTH_SCOPE) alongside gmail.modify -- quiet hours reads the owner's
# selected Google Calendars via this same client id/secret/token, never a second credential. Replaces
# GMAIL_CALENDAR_ICS_URL (a private "secret address" URL, deleted along with the ICS fetch/parse path
# it fed -- see UserProfile.mailbox_calendar_ids for where calendars are configured now).
GMAIL_OAUTH_CLIENT_ID = os.getenv('GMAIL_OAUTH_CLIENT_ID', '')
GMAIL_OAUTH_CLIENT_SECRET = os.getenv('GMAIL_OAUTH_CLIENT_SECRET', '')
# Local file the refresh token is written to and read from. Defaults to a `dachapply-*.json` name at
# the repo root so it rides the existing gitignore rule below (see .gitignore) instead of needing a
# new one -- same "local-only by construction" property as GMAIL_IMAP_APP_PASSWORD, just as a file
# instead of an env var (a long-lived refresh token belongs in neither `.env` nor git).
GMAIL_OAUTH_TOKEN_PATH = os.getenv('GMAIL_OAUTH_TOKEN_PATH', str(BASE_DIR.parent / 'dachapply-gmail-oauth-token.json'))

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
 'rest_framework','corsheaders','jobradar.apps.JobradarConfig'
]
MIDDLEWARE = [
 'django.middleware.security.SecurityMiddleware','whitenoise.middleware.WhiteNoiseMiddleware','corsheaders.middleware.CorsMiddleware',
 'django.middleware.common.CommonMiddleware','config.middleware.NoCacheHtmlMiddleware','django.middleware.csrf.CsrfViewMiddleware','config.middleware.SplitAdminSessionMiddleware','django.contrib.auth.middleware.AuthenticationMiddleware','jobradar.middleware.UserUsageMiddleware',
 'django.contrib.messages.middleware.MessageMiddleware','django.middleware.clickjacking.XFrameOptionsMiddleware'
]
ROOT_URLCONF='config.urls'
TEMPLATES=[{'BACKEND':'django.template.backends.django.DjangoTemplates','DIRS':[BASE_DIR/'templates', BASE_DIR.parent/'frontend'/'dist'],'APP_DIRS':True,'OPTIONS':{'context_processors':['django.template.context_processors.request','django.contrib.auth.context_processors.auth','django.contrib.messages.context_processors.messages']}}]
WSGI_APPLICATION='config.wsgi.application'

DATABASE_URL = os.getenv('DATABASE_URL')

# TASK-100: manage.py run from a laptop must not be able to silently reach production. The
# incident (2026-08-16) was DATABASE_URL arriving from the repo-root .env file, which holds the
# production Neon URL -- `unset DATABASE_URL` does nothing (the value comes from the file, not the
# shell) and `DB_NAME=...` is silently ignored (the sqlite branch below is unreachable while
# DATABASE_URL is truthy). Guarding on _env_file_keys rather than on "is this DEBUG" or "does the
# host look local" targets the actual danger: a value that showed up without anyone typing it this
# session. A DATABASE_URL exported in the shell for one command, or DATABASE_URL='' + DB_NAME=...
# (the old workaround, still supported), is a deliberate per-command choice and is left alone.
#
# The container and CI are unaffected without any extra check: neither ships a .env file (excluded
# by .gitignore and .dockerignore alike), so their DATABASE_URL always comes from the real process
# environment -- never recorded in _env_file_keys -- and this block never fires for them.
if local_db_guard_blocks(DATABASE_URL, _env_file_keys, env_bool('DACHAPPLY_ALLOW_PROD_DB', False)):
    raise ImproperlyConfigured(
        "DATABASE_URL came from a .env file, and that file can hold the production database. "
        "Refusing to start rather than risk a local manage.py command reaching it silently. "
        "Either clear DATABASE_URL in .env (optionally set DB_NAME=<path> to pick a local sqlite "
        "file -- manage.py falls back to backend/db.sqlite3 otherwise), or set "
        "DACHAPPLY_ALLOW_PROD_DB=1 for this command if you deliberately mean to reach that "
        "database. (Serving commands -- runserver, check_mailbox -- are exempt by design: per "
        "TASK-111 the local app runs against the same remote database as the deployed site.)"
    )

if DATABASE_URL:
    try:
        import dj_database_url
    except ImportError as exc:
        raise ImproperlyConfigured('DATABASE_URL requires dj-database-url to be installed.') from exc
    DATABASES = {
        'default': dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=int(os.getenv('DB_CONN_MAX_AGE', '600')),
            # A pooled/serverless Postgres (Neon) drops idle connections well inside conn_max_age.
            # Without a health check, a persisted connection is only recycled once it is old enough,
            # so the next query on a silently-dead socket fails instead of reconnecting.
            conn_health_checks=env_bool('DB_CONN_HEALTH_CHECKS', True),
            ssl_require=env_bool('DB_SSL_REQUIRE', not DEBUG),
        )
    }
else:
    if not DEBUG:
        raise ImproperlyConfigured('DATABASE_URL must be set for production when DEBUG=False.')
    DATABASES={'default': {'ENGINE': os.getenv('DB_ENGINE','django.db.backends.sqlite3'), 'NAME': os.getenv('DB_NAME', str(BASE_DIR/'db.sqlite3'))}}

# Throttle counters live in the cache. The default per-process LocMemCache gave every gunicorn
# worker its own counter, so a "5/hour" limit was really 5 x WEB_CONCURRENCY and reset on every
# revision swap. DatabaseCache is a store all workers already share and that survives a deploy;
# scripts/start-container.sh runs createcachetable next to migrate, and Django's test runner
# creates the table itself.
CACHES={'default':{'BACKEND':'django.core.cache.backends.db.DatabaseCache','LOCATION':os.getenv('CACHE_TABLE','dachapply_cache')}}

AUTH_PASSWORD_VALIDATORS=[{'NAME':'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},{'NAME':'django.contrib.auth.password_validation.MinimumLengthValidator'},{'NAME':'django.contrib.auth.password_validation.CommonPasswordValidator'},{'NAME':'django.contrib.auth.password_validation.NumericPasswordValidator'}]
LANGUAGE_CODE='en-us'; TIME_ZONE='Europe/Vienna'; USE_I18N=True; USE_TZ=True
STATIC_URL='/static/'; STATIC_ROOT=BASE_DIR/'staticfiles'; STATICFILES_DIRS=[]
STATICFILES_STORAGE='whitenoise.storage.CompressedManifestStaticFilesStorage'
FRONTEND_DIST=BASE_DIR.parent/'frontend'/'dist'
if FRONTEND_DIST.exists(): STATICFILES_DIRS.append(FRONTEND_DIST)
DEFAULT_AUTO_FIELD='django.db.models.BigAutoField'
DATA_UPLOAD_MAX_MEMORY_SIZE=8 * 1024 * 1024
REST_FRAMEWORK={
    'DEFAULT_AUTHENTICATION_CLASSES':['rest_framework.authentication.SessionAuthentication'],
    'DEFAULT_PERMISSION_CLASSES':['rest_framework.permissions.IsAuthenticated'],
    'DEFAULT_THROTTLE_RATES':{
        'login_ip': os.getenv('RATE_LIMIT_LOGIN_IP', '60/minute' if DEBUG else '10/minute'),
        'login_account': os.getenv('RATE_LIMIT_LOGIN_ACCOUNT', '20/minute' if DEBUG else '5/minute'),
        'register_ip': os.getenv('RATE_LIMIT_REGISTER_IP', '20/hour' if DEBUG else '5/hour'),
        'password_reset_ip': os.getenv('RATE_LIMIT_PASSWORD_RESET_IP', '20/hour' if DEBUG else '5/hour'),
        'password_reset_confirm_ip': os.getenv('RATE_LIMIT_PASSWORD_RESET_CONFIRM_IP', '20/hour' if DEBUG else '5/hour'),
        'password_reset_email': os.getenv('RATE_LIMIT_PASSWORD_RESET_EMAIL', '5/hour'),
        'email_verification_ip': os.getenv('RATE_LIMIT_EMAIL_VERIFICATION_IP', '60/hour' if DEBUG else '20/hour'),
        'public_submit_ip': os.getenv('RATE_LIMIT_PUBLIC_SUBMIT_IP', '60/hour' if DEBUG else '20/hour'),
        'import_user': os.getenv('RATE_LIMIT_IMPORT_USER', '120/hour' if DEBUG else '60/hour'),
        'cv_generation_user': os.getenv('RATE_LIMIT_CV_GENERATION_USER', '100/hour'),
    },
    'EXCEPTION_HANDLER':'jobradar.throttles.api_exception_handler',
}
CORS_ALLOW_CREDENTIALS=True
LOGIN_URL='/login'

FRONTEND_URL=os.getenv('FRONTEND_URL', 'http://localhost:5173' if DEBUG else '')
if not DEBUG and not FRONTEND_URL:
    raise ImproperlyConfigured('FRONTEND_URL must be set when DEBUG=False.')

# Email provider selection.
# EMAIL_PROVIDER=auto prefers Brevo if Brevo credentials are present, then a
# local SMTP provider, then the legacy EMAIL_* settings/defaults.
EMAIL_PROVIDER=os.getenv('EMAIL_PROVIDER', 'auto').strip().lower()

_brevo_login=os.getenv('BREVO_EMAIL_HOST_USER') or os.getenv('BREVO_SMTP_LOGIN') or (os.getenv('EMAIL_HOST_USER') if os.getenv('EMAIL_HOST') == 'smtp-relay.brevo.com' else '')
_brevo_key=os.getenv('BREVO_EMAIL_HOST_PASSWORD') or os.getenv('BREVO_SMTP_KEY') or (os.getenv('EMAIL_HOST_PASSWORD') if os.getenv('EMAIL_HOST') == 'smtp-relay.brevo.com' else '')
_brevo_from=os.getenv('BREVO_DEFAULT_FROM_EMAIL') or os.getenv('BREVO_FROM_EMAIL') or (os.getenv('DEFAULT_FROM_EMAIL') if os.getenv('EMAIL_HOST') == 'smtp-relay.brevo.com' else '')
_brevo_configured=bool(_brevo_login and _brevo_key and _brevo_from)

_local_host=os.getenv('LOCAL_EMAIL_HOST') or os.getenv('LOCAL_SMTP_HOST')
_local_user=os.getenv('LOCAL_EMAIL_HOST_USER') or os.getenv('LOCAL_SMTP_USER')
_local_password=os.getenv('LOCAL_EMAIL_HOST_PASSWORD') or os.getenv('LOCAL_SMTP_PASSWORD')
_local_from=os.getenv('LOCAL_DEFAULT_FROM_EMAIL') or os.getenv('LOCAL_FROM_EMAIL')
_local_configured=bool(_local_host and _local_user and _local_password and _local_from)

if EMAIL_PROVIDER in ('console', 'local-console'):
    if not DEBUG:
        raise ImproperlyConfigured('EMAIL_PROVIDER=console is only allowed when DEBUG=True.')
    DEFAULT_FROM_EMAIL=os.getenv('DEFAULT_FROM_EMAIL', 'DACHApply <local@dachapply.test>')
    EMAIL_BACKEND='django.core.mail.backends.console.EmailBackend'
    EMAIL_HOST=''
    EMAIL_USE_TLS=False
    EMAIL_USE_SSL=False
    EMAIL_PORT=25
    EMAIL_HOST_USER=''
    EMAIL_HOST_PASSWORD=''
elif EMAIL_PROVIDER == 'brevo' or (EMAIL_PROVIDER == 'auto' and _brevo_configured):
    DEFAULT_FROM_EMAIL=_brevo_from
    EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST=os.getenv('BREVO_EMAIL_HOST', 'smtp-relay.brevo.com')
    EMAIL_USE_TLS=env_bool('BREVO_EMAIL_USE_TLS', True)
    EMAIL_USE_SSL=env_bool('BREVO_EMAIL_USE_SSL', False)
    EMAIL_PORT=int(os.getenv('BREVO_EMAIL_PORT', '587'))
    EMAIL_HOST_USER=_brevo_login
    EMAIL_HOST_PASSWORD=normalize_smtp_password(EMAIL_HOST, _brevo_key)
elif EMAIL_PROVIDER in ('local', 'local-smtp') or (EMAIL_PROVIDER == 'auto' and _local_configured):
    DEFAULT_FROM_EMAIL=_local_from
    EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST=_local_host
    EMAIL_USE_TLS=env_bool('LOCAL_EMAIL_USE_TLS', env_bool('LOCAL_SMTP_USE_TLS', True))
    EMAIL_USE_SSL=env_bool('LOCAL_EMAIL_USE_SSL', env_bool('LOCAL_SMTP_USE_SSL', False))
    EMAIL_PORT=int(os.getenv('LOCAL_EMAIL_PORT') or os.getenv('LOCAL_SMTP_PORT') or '587')
    EMAIL_HOST_USER=_local_user
    EMAIL_HOST_PASSWORD=normalize_smtp_password(EMAIL_HOST, _local_password)
else:
    DEFAULT_FROM_EMAIL=os.getenv('DEFAULT_FROM_EMAIL', 'noreply@localhost' if DEBUG else '')
    EMAIL_BACKEND=os.getenv('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend' if DEBUG else 'django.core.mail.backends.smtp.EmailBackend')
    EMAIL_HOST=os.getenv('EMAIL_HOST', 'localhost' if DEBUG else '')
    EMAIL_USE_TLS=env_bool('EMAIL_USE_TLS', not DEBUG)
    EMAIL_USE_SSL=env_bool('EMAIL_USE_SSL', False)
    EMAIL_PORT=int(os.getenv('EMAIL_PORT', '587' if EMAIL_USE_TLS else '25'))
    EMAIL_HOST_USER=os.getenv('EMAIL_HOST_USER','')
    EMAIL_HOST_PASSWORD=normalize_smtp_password(EMAIL_HOST, os.getenv('EMAIL_HOST_PASSWORD',''))
EMAIL_TIMEOUT=int(os.getenv('EMAIL_TIMEOUT', '10'))
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

# --- Error alerting -----------------------------------------------------------------------------
# Unhandled 500s used to be invisible, not merely hard to find. Django's default console handler
# carries a require_debug_true filter, so with DEBUG=False a 500 traceback went nowhere at all
# (measured: emitting one under DEFAULT_LOGGING produced no output on either stream), and the
# default mail_admins handler was a no-op because ADMINS was never set. gunicorn is started without
# --access-logfile, so not even a status line was left behind. The uptime monitor sees "down", not
# "erroring".
#
# No new dependency for this. Sentry would add a monkeypatching SDK plus an account and a DSN to
# deliver a signal over a channel this app already has working (Brevo SMTP, exercised by password
# reset). What Sentry gives that this does not: grouping, search and retention -- accepted losses.
# Its rate limiting is the one feature with a failure mode if missing, so it is replaced below.
#
# Inert until configured: with ERROR_ALERT_EMAILS unset, ADMINS is empty and AdminEmailHandler.emit
# returns immediately. The only behaviour change with nothing set is that ERROR tracebacks now reach
# stdout in production, where previously they reached nothing.
ADMINS = [('DACHApply alerts', address) for address in env_list('ERROR_ALERT_EMAILS')]
# Django's default SERVER_EMAIL is root@localhost, which a relay like Brevo rejects because it is not
# a verified sender -- the alert would bounce instead of arriving.
SERVER_EMAIL = os.getenv('SERVER_EMAIL') or DEFAULT_FROM_EMAIL
EMAIL_SUBJECT_PREFIX = os.getenv('EMAIL_SUBJECT_PREFIX', '[DACHApply] ')
ERROR_ALERT_COOLDOWN_SECONDS = int(os.getenv('ERROR_ALERT_COOLDOWN_SECONDS', '300'))
# TASK-157: the alert above attaches a full settings dump, and Django decides what to mask by the
# setting's NAME (API|TOKEN|KEY|SECRET|PASS|SIGNATURE|HTTP_COOKIE). DATABASE_URL matches none of
# them, so the 2026-08-20 alert that finally proved this channel works also mailed the production
# database connection string through a third-party relay. See config/error_filters for the explicit
# extra list and for which settings were checked and deliberately left visible.
DEFAULT_EXCEPTION_REPORTER_FILTER = 'config.error_filters.DachApplyExceptionReporterFilter'

# TASK-160: the mailbox check itself runs on the owner's own machine (that is where the Gmail
# credentials live), so it can never alert on its own -- DEBUG=True there blocks the mail_admins
# handler above, and there is no SMTP configured locally either. jobradar.views.mailbox_health, on
# the DEPLOYED site, reads the same database the local check writes to and alerts instead. This
# threshold is a fixed, generous default rather than derived from
# UserProfile.mailbox_check_cadence_minutes: quiet hours and a closed check window already create
# legitimate gaps between successful runs, and deriving the threshold from cadence is a refinement
# for later, not a requirement now (see the task's Implementation Notes).
MAILBOX_STALE_ALERT_HOURS = int(os.getenv('MAILBOX_STALE_ALERT_HOURS', '24'))

_alert_last_sent = {}


def _alert_key(record):
    """Group by where the exception was actually raised, so distinct bugs alert independently."""
    exc_type, _, tb = record.exc_info or (None, None, None)
    while tb is not None and tb.tb_next is not None:
        tb = tb.tb_next
    if tb is not None:
        return f'{exc_type.__name__}:{tb.tb_frame.f_code.co_filename}:{tb.tb_lineno}'
    return f'{record.name}:{record.getMessage()}'


class ErrorAlertCooldown:
    """Send at most one alert per distinct failure per ERROR_ALERT_COOLDOWN_SECONDS.

    A crash loop on a hot path would otherwise send one email per request and burn the shared Brevo
    quota that password-reset mail depends on: the alerting would break the thing it is watching.

    Deliberately never raises. A logging filter runs outside the try/except that guards emit(), so an
    exception here would abort the request being reported on. It fails open for the same reason -- a
    missed cooldown costs a duplicate email, a swallowed record costs the alert.

    ponytail: the window is per process, so N gunicorn workers can each send one alert per window.
    A shared counter would have to live in the DatabaseCache, and the database going down is exactly
    the failure most likely to cause the storm -- the cooldown must not depend on it.
    """

    def filter(self, record):
        if ERROR_ALERT_COOLDOWN_SECONDS <= 0:
            return True
        try:
            key = _alert_key(record)
            now = time.monotonic()
            last = _alert_last_sent.get(key)
            if last is not None and now - last < ERROR_ALERT_COOLDOWN_SECONDS:
                return False
            if len(_alert_last_sent) > 500:
                _alert_last_sent.clear()
            _alert_last_sent[key] = now
        except Exception:
            pass
        return True


LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        # Order matters: logging stops at the first filter that rejects, so the cheap
        # production-only check runs before any bookkeeping.
        'require_debug_false': {'()': 'django.utils.log.RequireDebugFalse'},
        'error_alert_cooldown': {'()': ErrorAlertCooldown},
    },
    'formatters': {'app': {'format': '[{asctime}] {levelname} {name} {message}', 'style': '{'}},
    'handlers': {
        # No require_debug_true filter, unlike Django's default console handler: production stdout
        # is where the traceback has to land when the email channel is not configured.
        'console': {'class': 'logging.StreamHandler', 'formatter': 'app'},
        'mail_admins': {
            'level': 'ERROR',
            'class': 'django.utils.log.AdminEmailHandler',
            'filters': ['require_debug_false', 'error_alert_cooldown'],
        },
    },
    'loggers': {
        # django.request logs 4xx at WARNING and 5xx at ERROR, so an ERROR-level handler already
        # excludes 404s and throttled 429s. Verified in jobradar/tests/test_error_alerting.py rather
        # than assumed. These loggers keep propagate=True: the parent 'django' handler prints them,
        # and pytest's caplog needs records to reach the root logger.
        'django': {'handlers': ['console'], 'level': 'INFO'},
        'django.request': {'handlers': ['mail_admins'], 'level': 'INFO'},
        # django.security.* logs SuspiciousOperation at ERROR -- including DisallowedHost, which any
        # bot probing the container by IP triggers. No handler of its own, so it propagates to
        # 'django' above and lands on the console only: that is log noise, not a page.
        'django.security': {'level': 'INFO'},
        # Application logger.exception() sites are the silent-breakage class this task exists for:
        # a password-reset mail that fails to send returns 200 to the user and 500s nothing.
        'jobradar': {'handlers': ['console', 'mail_admins'], 'level': 'INFO'},
    },
}
