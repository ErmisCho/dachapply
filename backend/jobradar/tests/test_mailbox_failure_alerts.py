"""TASK-289: mailbox check failures are never silent -- a board-banner condition and one alert email
per transition. Every MailboxRun is a plain row or a run_check() with an in-memory transport; no Gmail
call, and mail goes to the locmem outbox (conftest's autouse _never_send_real_email).
"""
from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.core import mail
from django.utils import timezone
from rest_framework.test import APIClient

from jobradar.models import MailboxRun
from jobradar.services.mailbox import mailbox_health, run_check
from jobradar.services.prompt_builder import user_profile_settings

INVALID_GRANT = 'Gmail OAuth token request failed with HTTP 400: {"error": "invalid_grant", "error_description": "Token has been expired or revoked."}'


@pytest.fixture
def owner(db, settings):
    settings.GMAIL_IMAP_USER = 'owner@example.test'
    settings.GMAIL_IMAP_APP_PASSWORD = 'fake-app-password'
    settings.GMAIL_OAUTH_CLIENT_ID = settings.GMAIL_OAUTH_CLIENT_SECRET = ''
    settings.CODEX_CV_OWNER_EMAIL = 'owner@example.test'
    settings.ADMINS = [('DACHApply alerts', 'ops@example.com')]
    user = User.objects.create_user('owner@example.test', email='owner@example.test', password='pw', is_staff=True)
    user_profile_settings(user)
    return user


def make_run(hours_ago, error='', skipped=False):
    run = MailboxRun.objects.create(error=error, skipped=skipped, skip_reason='outside_window' if skipped else '')
    when = timezone.now() - timedelta(hours=hours_ago)
    MailboxRun.objects.filter(pk=run.pk).update(started_at=when, finished_at=when)
    return MailboxRun.objects.get(pk=run.pk)


def test_latest_error_is_failing_with_plain_words_and_when_it_started(db):
    make_run(10)
    first_error = make_run(5, error=INVALID_GRANT)
    make_run(1, error=INVALID_GRANT)
    health = mailbox_health(enabled=True)
    assert health['reason'] == 'invalid_grant'
    assert health['message'] == 'Gmail login expired'
    assert 'gmail_oauth_setup' in health['action']
    assert health['since'] == first_error.started_at


@pytest.mark.parametrize('error,reason,message', [
    ('Gmail API GET x failed with HTTP 403: {"reason": "rateLimitExceeded"}', 'rate_limit', 'Gmail rate limit'),
    ('Could not reach Gmail API at https://x: <urlopen error timed out>', 'network', "Couldn't reach Gmail"),
    ('The read operation timed out', 'network', "Couldn't reach Gmail"),
    ('Something odd\nTraceback line', 'other', 'Something odd'),
])
def test_error_categories(db, error, reason, message):
    make_run(1, error=error)
    health = mailbox_health(enabled=True)
    assert (health['reason'], health['message']) == (reason, message)


def test_skipped_runs_neither_hide_a_failure_nor_count_as_success(db):
    make_run(30)
    make_run(3, error=INVALID_GRANT)
    make_run(1, skipped=True)  # outside_window: must not mask the error above
    assert mailbox_health(enabled=True)['reason'] == 'invalid_grant'
    MailboxRun.objects.filter(error=INVALID_GRANT).delete()
    # only skips since a success 30 h ago: stale, the skips are not evidence of a working check
    health = mailbox_health(enabled=True)
    assert health['reason'] == 'stale'
    assert health['since'] == MailboxRun.objects.get(skipped=False).finished_at


def test_stale_only_while_checks_are_enabled(db):
    make_run(25)
    assert mailbox_health(enabled=True)['reason'] == 'stale'
    assert mailbox_health(enabled=False) is None
    assert mailbox_health(enabled=True, now=timezone.now() - timedelta(hours=2)) is None


def test_recovers_on_the_next_successful_run(db):
    make_run(2, error=INVALID_GRANT)
    assert mailbox_health(enabled=True) is not None
    make_run(1)
    assert mailbox_health(enabled=True) is None


class _Boom:
    def fetch_new(self, last_uid):
        raise RuntimeError(INVALID_GRANT)


class _Ok:
    def fetch_new(self, last_uid):
        return []


def test_one_mail_when_checks_start_failing_and_one_when_they_recover(owner, monkeypatch):
    monkeypatch.setattr('jobradar.services.followup_digest.reconcile_sent_followups', lambda transport, owner: None)
    run_check(force=True, transport=_Ok())
    assert mail.outbox == []
    for _ in range(3):
        run_check(force=True, transport=_Boom())
    profile = user_profile_settings(owner)
    profile.mailbox_check_enabled = False
    profile.save(update_fields=['mailbox_check_enabled'])
    run_check(force=True, transport=_Boom())  # skipped: no mail, no state change
    profile.mailbox_check_enabled = True
    profile.save(update_fields=['mailbox_check_enabled'])
    run_check(force=True, transport=_Boom())
    assert [m.subject for m in mail.outbox] == ['[DACHApply] Mailbox check failing: Gmail login expired']
    assert 'gmail_oauth_setup' in mail.outbox[0].body
    run_check(force=True, transport=_Ok())
    run_check(force=True, transport=_Ok())
    assert [m.subject for m in mail.outbox][1:] == ['[DACHApply] Mailbox check recovered']


def test_status_endpoint_carries_health_for_the_owner(owner):
    make_run(1, error=INVALID_GRANT)
    client = APIClient()
    client.force_authenticate(owner)
    health = client.get('/api/mailbox-runs/status/').data['health']
    assert health['reason'] == 'invalid_grant'
