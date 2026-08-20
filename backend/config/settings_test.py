"""Django settings for the test run only (DJANGO_SETTINGS_MODULE for pytest).

DATABASE_URL is blanked and DEBUG defaulted to '1' in os.environ BEFORE the
star-import below, because config.settings reads both at import time: with
DATABASE_URL set (e.g. from the repo-root .env, which load_env_file() applies
via os.environ.setdefault -- so it only takes effect if nothing already set
the variable), settings.py imports dj_database_url and points DATABASES at
the production Neon host; if dj_database_url isn't installed it raises
ImproperlyConfigured instead. Setting DATABASE_URL='' here (before import)
wins over the .env file and forces settings.py down its sqlite fallback
branch on every machine, whether or not dj_database_url is installed.

Even so, DATABASES is pinned below to a disposable in-memory sqlite database
rather than trusting that fallback (which still reads DB_ENGINE/DB_NAME from
the environment), and CODEX_CV_WORKSPACE is pinned to a fresh disposable temp
directory so no test can compile into, cache into, or write benchmark/report
files into the real C:/latex workspace even if it forgets its own override.
Both are safe to lose on an interrupted run: sqlite ':memory:' evaporates
with the process, and the temp directory is never relied on for content --
tests that need real files use their own tmp_path fixture.
"""
import os
import tempfile

os.environ['DATABASE_URL'] = ''
os.environ.setdefault('DEBUG', '1')

from .settings import *  # noqa: F401,F403

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

CODEX_CV_WORKSPACE = tempfile.mkdtemp(prefix='dachapply-test-workspace-')

# The mailbox feature is "configured" when EITHER the IMAP pair or the OAuth pair is set, and both
# pairs are read from the developer's own .env. Left alone, a developer who has actually set up the
# Gmail check gets different test results from one who has not -- and the difference shows up as
# tests failing locally while passing in CI, which ships no .env. That is the same shape as the
# untracked-personal-file dependency CI caught once before, so it is neutralised here rather than
# left to each test to remember. Any test that wants the feature configured sets these itself via
# the `settings` fixture.
GMAIL_IMAP_USER = ''
GMAIL_IMAP_APP_PASSWORD = ''
GMAIL_OAUTH_CLIENT_ID = ''
GMAIL_OAUTH_CLIENT_SECRET = ''
