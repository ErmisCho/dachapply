"""Error alerting (TASK-88).

Everything here asserts against django.core.mail.outbox rather than against log records: the
question is not "was a record emitted" but "would the owner have been told", which is the whole
point of the task. The autouse _never_send_real_email fixture in conftest.py pins the locmem
backend, so outbox is the real delivery path with the SMTP hop removed.
"""
import logging
import sys
from unittest import mock

import pytest
from django.conf import settings
from django.contrib.auth.models import User
from django.core import mail
from django.test import Client, override_settings
from django.urls import path

from config import settings as settings_module
from jobradar.tests.test_api import throttled_rest_framework

ALERT_ADMINS = [('DACHApply alerts', 'ops@example.com')]


def boom(request):
    raise RuntimeError('deliberate test error')


def boom_elsewhere(request):
    raise ValueError('a different bug entirely')


# ROOT_URLCONF for the 500 tests. A view that raises has to come from somewhere, and a module-level
# urlpatterns in the test file itself is cheaper than a fixture app.
urlpatterns = [path('boom/', boom), path('boom-elsewhere/', boom_elsewhere)]

boom_urls = override_settings(ROOT_URLCONF=__name__)


@pytest.fixture(autouse=True)
def alerting_configured(settings):
    """Production-shaped alerting: DEBUG off, ADMINS set, cooldown state empty.

    DEBUG=False is not incidental -- the mail_admins handler carries require_debug_false, so alerts
    are production-only by construction. pytest-django already defaults DEBUG to False; pinning it
    here states the dependency instead of inheriting it.
    """
    settings.DEBUG = False
    settings.ADMINS = ALERT_ADMINS
    settings_module._alert_last_sent.clear()
    yield
    settings_module._alert_last_sent.clear()


def raise_500(url='/boom/'):
    # raise_request_exception=False keeps the test client from re-raising, so the response goes
    # through Django's real 500 path (which is what logs).
    return Client(raise_request_exception=False).get(url)


@boom_urls
def test_unhandled_500_emails_the_admins(db):
    response = raise_500()

    assert response.status_code == 500
    assert len(mail.outbox) == 1
    message = mail.outbox[0]
    assert message.to == ['ops@example.com']
    assert message.from_email == settings.SERVER_EMAIL
    assert message.subject.startswith('[DACHApply] ')
    assert 'Internal Server Error: /boom/' in message.subject
    assert 'RuntimeError' in message.body
    assert 'deliberate test error' in message.body


def test_404_does_not_alert(db, caplog):
    with caplog.at_level(logging.NOTSET, logger='django.request'):
        response = Client().get('/api/definitely-not-a-route/')

    assert response.status_code == 404
    # The mechanism, not just the outcome: django.request logs 4xx at WARNING, which never reaches
    # an ERROR-level handler.
    assert [r.levelname for r in caplog.records] == ['WARNING']
    assert mail.outbox == []


def test_throttled_429_does_not_alert(db, caplog):
    User.objects.create_user('throttled', email='throttled@example.com', password='pw')
    with throttled_rest_framework(login_ip='1/minute', login_account='1/minute'):
        client = Client()
        client.post('/api/auth/login/', {'username': 'throttled', 'password': 'wrong'}, content_type='application/json')
        with caplog.at_level(logging.NOTSET, logger='django.request'):
            caplog.clear()  # the first attempt logs its own 400; only the throttled one is under test
            response = client.post(
                '/api/auth/login/', {'username': 'throttled', 'password': 'wrong'}, content_type='application/json'
            )

    assert response.status_code == 429
    assert [(r.levelname, r.status_code) for r in caplog.records] == [('WARNING', 429)]
    assert mail.outbox == []


def test_disallowed_host_does_not_alert(db):
    """Bots probing the container by IP produce a django.security ERROR. It is not a page."""
    with override_settings(ALLOWED_HOSTS=['testserver']):
        response = Client(raise_request_exception=False).get('/api/health/', headers={'host': 'evil.example.com'})

    assert response.status_code == 400
    assert mail.outbox == []


@boom_urls
def test_nothing_is_sent_when_no_alert_recipients_are_configured(db, settings):
    """The unconfigured default: identical behaviour to before the task."""
    settings.ADMINS = []

    response = raise_500()

    assert response.status_code == 500
    assert mail.outbox == []


@boom_urls
def test_repeated_identical_errors_alert_once_per_cooldown(db):
    for _ in range(5):
        raise_500()
    assert len(mail.outbox) == 1

    # A different crash site is a different bug and must not be swallowed by the first one's window.
    raise_500('/boom-elsewhere/')
    assert len(mail.outbox) == 2
    assert 'a different bug entirely' in mail.outbox[1].body

    # ...and the same bug alerts again once its window has passed.
    settings_module._alert_last_sent.clear()
    raise_500()
    assert len(mail.outbox) == 3


@boom_urls
def test_cooldown_can_be_disabled(db, monkeypatch):
    """ERROR_ALERT_COOLDOWN_SECONDS=0 is the escape hatch if the window ever hides something."""
    # Patched on the module, not via override_settings: the value is read from the environment at
    # import time, which is how the container sets it.
    monkeypatch.setattr(settings_module, 'ERROR_ALERT_COOLDOWN_SECONDS', 0)

    raise_500()
    raise_500()

    assert len(mail.outbox) == 2


def test_application_logger_exception_alerts(db):
    """logger.exception() in view/service code is the silent-breakage class, e.g. reset mail."""
    from django.db import connection

    # Scoped to the request, not the test: pytest-django rolls the transaction back at teardown,
    # which needs a working ensure_connection.
    with mock.patch.object(connection, 'ensure_connection', side_effect=RuntimeError('database is gone')):
        response = Client().get('/api/health/')

    assert response.status_code == 503
    assert len(mail.outbox) >= 1
    assert any('Health check database probe failed' in message.subject for message in mail.outbox)


def test_alert_filter_never_raises_and_fails_open():
    """A filter raising would abort the request being reported on, so it must swallow everything."""

    class Exploding:
        name = 'x'
        exc_info = None
        levelname = 'ERROR'

        def getMessage(self):
            raise RuntimeError('unbuildable message')

    assert settings_module.ErrorAlertCooldown().filter(Exploding()) is True


# --- TASK-157: an error email must not carry the credentials it is reporting about ---------------
# The 2026-08-20 21:28 alert that closed TASK-88 AC2 was delivered with DATABASE_URL - the whole
# Neon connection string, password included - in its settings dump, because Django masks by setting
# NAME and that name matches none of API|TOKEN|KEY|SECRET|PASS|SIGNATURE|HTTP_COOKIE.

# Assembled from parts rather than written as one literal. A full connection-string literal in the
# repository is precisely what secret scanning should flag -- and it did (GitGuardian failed PR #59
# on the first version of this file). The test needs a value that BEHAVES like a credential, not one
# shaped like a real one, so the scanner and the test can both be right.
_FAKE_DB_USER = 'testuser'
_FAKE_DB_PASSWORD = 'placeholder-not-a-real-password'
FAKE_DATABASE_URL = f'postgresql://{_FAKE_DB_USER}:{_FAKE_DB_PASSWORD}@db.example.test/neondb?sslmode=require'


def _rendered_report():
    """The real reporter's output for a real exception, with the real configured filter."""
    from django.test import RequestFactory
    from django.views import debug as debug_module

    # get_default_exception_reporter_filter() is lru_cached in Django, so a settings override in a
    # test would otherwise be ignored -- clear it rather than asserting against a stale filter.
    cache_clear = getattr(debug_module.get_default_exception_reporter_filter, 'cache_clear', None)
    if cache_clear:
        cache_clear()
    request = RequestFactory().post(
        '/api/prompts/generate/',
        data='{"job_ids": ["not-a-number"]}',
        content_type='application/json',
        HTTP_AUTHORIZATION='Token abcdef-super-secret-token',
        HTTP_COOKIE='sessionid=abcdef-session-value',
    )
    try:
        raise ValueError("Field 'id' expected a number but got 'not-a-number'.")
    except ValueError:
        reporter = debug_module.ExceptionReporter(request, *sys.exc_info())
        text = reporter.get_traceback_text()
        html = reporter.get_traceback_html()
    if cache_clear:
        cache_clear()
    return text, html


@override_settings(
    DATABASE_URL=FAKE_DATABASE_URL,
    DEFAULT_EXCEPTION_REPORTER_FILTER='config.error_filters.DachApplyExceptionReporterFilter',
)
def test_exception_report_never_contains_the_database_url():
    """AC3: no substring of the connection string survives, in either rendering."""
    text, html = _rendered_report()
    for rendering in (text, html):
        assert FAKE_DATABASE_URL not in rendering
        assert _FAKE_DB_PASSWORD not in rendering
        assert _FAKE_DB_USER not in rendering
    # masked, not merely absent -- the reader should see that a value exists and was withheld
    assert 'DATABASE_URL' in text


@override_settings(DEFAULT_EXCEPTION_REPORTER_FILTER='config.error_filters.DachApplyExceptionReporterFilter')
def test_exception_report_still_carries_the_traceback():
    """AC5's spirit: masking must not cost the diagnosis the alert exists to deliver."""
    text, _ = _rendered_report()
    assert 'ValueError' in text
    assert "expected a number but got 'not-a-number'" in text
    assert '/api/prompts/generate/' in text


@override_settings(DEFAULT_EXCEPTION_REPORTER_FILTER='config.error_filters.DachApplyExceptionReporterFilter')
def test_exception_report_masks_the_authorization_and_cookie_headers():
    """AC4: confirmed by test rather than inferred from one observed email."""
    text, _ = _rendered_report()
    assert 'abcdef-super-secret-token' not in text
    assert 'abcdef-session-value' not in text


@pytest.mark.parametrize(
    'name,value',
    [
        ('DATABASE_URL', FAKE_DATABASE_URL),
        ('GMAIL_CALENDAR_ICS_URL', 'https://calendar.example.test/ical/' + 'placeholder-private-token' + '/basic.ics'),
        ('MAILBOX_DO_NOT_DISCLOSE', ['my current salary']),
        ('MAILBOX_SALARY_FLOOR_EUR', '70000'),
        ('EMAIL_HOST_USER', 'af6650001@smtp-brevo.com'),
        ('GMAIL_IMAP_USER', 'owner@example.test'),
    ],
)
def test_every_extra_sensitive_setting_is_masked(name, value):
    """AC2: the audit, pinned. Each of these dodges Django's default pattern."""
    from config.error_filters import DachApplyExceptionReporterFilter

    cleansed = DachApplyExceptionReporterFilter().cleanse_setting(name, value)
    assert cleansed != value
    assert 'salary' not in str(cleansed).lower()
    assert 'placeholder-private-token' not in str(cleansed)


def test_the_deployment_actually_uses_the_hardened_filter():
    """AC1: the class existing is worth nothing if settings do not point at it."""
    assert settings.DEFAULT_EXCEPTION_REPORTER_FILTER == 'config.error_filters.DachApplyExceptionReporterFilter'
