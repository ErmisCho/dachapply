"""TASK-160: the deployed site's mailbox watchdog.

The check itself (services/mailbox.py's run_check) runs on the owner's own machine and can never
alert on its own -- DEBUG=True there blocks the require_debug_false-gated mail_admins handler
test_error_alerting.py covers, and there is no SMTP configured locally either. jobradar.views.
mailbox_health, reachable on the DEPLOYED site, computes health from MailboxRun rows alone and
sends through django.core.mail directly instead.

Every test here asserts on django.core.mail.outbox, same idiom as test_error_alerting.py -- the
question is "would the owner have been told", not "was some record written". conftest.py's autouse
_never_send_real_email fixture already pins the locmem backend, so outbox is the real delivery path
with only the SMTP hop removed. No test sends real mail or contacts a real mailbox (AC8): every
MailboxRun here is a plain objects.create() row, never a Gmail call.
"""
import pytest
from django.core import mail
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient

from jobradar.models import MailboxRun

ALERT_ADMINS = [('DACHApply alerts', 'ops@example.com')]


@pytest.fixture(autouse=True)
def _watchdog_env(settings, db):
    """A known alert recipient and a clean cooldown cache for every test.

    CACHES is DatabaseCache (see config/settings.py), which persists across tests in the same run
    unless cleared -- same reasoning as test_invite_codes.py's identical `cache.clear()` fixture.
    """
    settings.ADMINS = ALERT_ADMINS
    cache.clear()


def probe():
    return APIClient().get('/api/mailbox-health/')


def make_run(hours_ago, error='', finished=True):
    """A MailboxRun as if it started/finished `hours_ago` hours in the past.

    started_at is auto_now_add, so the backdate has to go through .update() (bypasses save()) --
    same trick test_mailbox.py and test_mailbox_panel.py already use for this exact model.
    """
    run = MailboxRun.objects.create(error=error)
    when = timezone.now() - timezone.timedelta(hours=hours_ago)
    MailboxRun.objects.filter(pk=run.pk).update(started_at=when, finished_at=when if finished else None)
    return run


def test_healthy_when_a_recent_run_succeeded():
    make_run(hours_ago=1)

    response = probe()

    assert response.status_code == 200
    assert response.data == {'status': 'ok'}
    assert mail.outbox == []


def test_failing_latest_run_alerts_with_the_remedy():
    make_run(hours_ago=1)  # an earlier healthy run must not mask the fresher failure
    make_run(hours_ago=0, error='Gmail OAuth error: invalid_grant')

    response = probe()

    assert response.status_code == 200
    assert response.data == {'status': 'failing'}
    assert len(mail.outbox) == 1
    message = mail.outbox[0]
    assert message.to == ['ops@example.com']
    assert 'mailbox' in message.subject.lower()
    # AC3: the exact re-authorization command, and the publish-removes-the-7-day-expiry sentence.
    assert 'manage.py gmail_oauth_setup' in message.body
    assert 'publish' in message.body.lower() and 'consent screen' in message.body.lower()
    assert '7' in message.body and 'expir' in message.body.lower()


def test_stale_when_no_successful_run_within_the_window():
    make_run(hours_ago=30, error='')  # succeeded, but outside the default 24h window

    response = probe()

    assert response.status_code == 200
    assert response.data == {'status': 'stale'}
    assert len(mail.outbox) == 1
    assert 'manage.py gmail_oauth_setup' in mail.outbox[0].body


def test_no_runs_at_all_is_also_stale():
    """AC1's second failure mode: nothing ran, which looks identical to 'no new mail' from the UI
    but is exactly the silent case this task exists to catch."""
    response = probe()

    assert response.status_code == 200
    assert response.data == {'status': 'stale'}
    assert len(mail.outbox) == 1


def test_a_skipped_run_still_counts_as_evidence_the_checker_is_alive():
    """A graceful skip (quiet hours, disabled, outside the window) finishes with no error -- it is
    not a Gmail fetch, but it proves the process that runs the check executed recently."""
    make_run(hours_ago=1, error='', finished=True)

    response = probe()

    assert response.data == {'status': 'ok'}
    assert mail.outbox == []


def test_second_probe_inside_the_cooldown_sends_nothing_more():
    make_run(hours_ago=0, error='boom')

    first = probe()
    second = probe()

    assert first.status_code == second.status_code == 200
    assert first.data == second.data == {'status': 'failing'}
    assert len(mail.outbox) == 1


def test_nothing_sent_when_no_recipients_are_configured(settings):
    settings.ADMINS = []
    make_run(hours_ago=0, error='boom')

    response = probe()

    assert response.status_code == 200
    assert response.data == {'status': 'failing'}
    assert mail.outbox == []


def test_response_never_leaks_anything_about_the_mailbox():
    """AC6: coarse status only -- no subjects, senders, counts, or the raw error text."""
    make_run(hours_ago=0, error='Gmail OAuth error for owner@example.test: invalid_grant')

    response = probe()

    assert set(response.data.keys()) == {'status'}
    raw = response.content.decode()
    assert 'owner@example.test' not in raw
    assert 'invalid_grant' not in raw
