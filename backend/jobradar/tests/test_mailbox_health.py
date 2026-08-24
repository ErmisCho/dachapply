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


# TASK-185. The cooldown existed and worked; it was borrowed from TASK-88's ERROR_ALERT_COOLDOWN_
# SECONDS, which defaults to 300. Five minutes is right for a transient exception and wrong for a
# condition that only alerts once it is a day old (MAILBOX_STALE_ALERT_HOURS) and then persists until
# a human runs an interactive OAuth command -- the owner received 83 identical emails over three and
# a half days. These pin the duration, the per-status key and the recovery clear, so the next person
# who "simplifies" this back onto the shared setting fails a test instead of the owner's inbox.
def test_the_mailbox_alert_uses_its_own_cooldown_not_the_error_alert_floor(settings):
    """The whole defect in one assertion: a 5-minute error floor must not govern this alert."""
    assert settings.MAILBOX_HEALTH_ALERT_COOLDOWN_SECONDS >= 3600
    assert settings.MAILBOX_HEALTH_ALERT_COOLDOWN_SECONDS != settings.ERROR_ALERT_COOLDOWN_SECONDS


def test_a_persisting_failure_is_not_re_alerted_until_the_cooldown_expires(settings):
    """Controlled by shrinking the window and expiring the key, never by sleeping."""
    settings.MAILBOX_HEALTH_ALERT_COOLDOWN_SECONDS = 900
    make_run(hours_ago=0, error='boom')

    probe()
    probe()
    assert len(mail.outbox) == 1, 'a repeat probe inside the window must send nothing'

    # the window passing is the only thing that changes; the condition is untouched
    cache.delete('mailbox_health_watchdog_alert_sent:failing')
    probe()
    assert len(mail.outbox) == 2, 'once the window has passed the owner is told again'


def test_a_change_of_status_is_not_swallowed_by_the_other_status_window():
    """stale and failing are different news; one must not silence the other."""
    make_run(hours_ago=48)                      # a successful run, but long ago -> stale
    probe()
    assert len(mail.outbox) == 1
    assert 'stale' in mail.outbox[0].subject or 'No successful run' in mail.outbox[0].body

    make_run(hours_ago=0, error='boom')         # now actively failing, inside the stale window
    probe()
    assert len(mail.outbox) == 2, 'a failure after a staleness alert is new information'


def test_recovery_clears_the_cooldown_so_the_next_failure_alerts_promptly():
    make_run(hours_ago=0, error='boom')
    probe()
    assert len(mail.outbox) == 1

    make_run(hours_ago=0)                       # recovered: no mail, deliberately
    probe()
    assert len(mail.outbox) == 1, 'recovery is silent - the owner just fixed it by hand'

    make_run(hours_ago=0, error='boom again')   # and the next failure is not stuck behind the window
    probe()
    assert len(mail.outbox) == 2


def test_the_subject_carries_the_reason_so_repeats_are_distinguishable():
    """83 identical subject lines is what turned a real alert into noise."""
    make_run(hours_ago=48)
    probe()

    assert 'DACHApply mailbox check needs attention' in mail.outbox[0].subject
    assert mail.outbox[0].subject != 'DACHApply mailbox check needs attention'


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
