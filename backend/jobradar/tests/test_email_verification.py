"""TASK-93: registration proves the address, and stops answering "does this one exist?".

The enumeration tests here compare *responses*, not messages. Rewording the old
'Friend username or email not found' would have left the oracle intact -- a 400 against a 201, or a
friend's username echoed back on a hit, answers the question just as well as the sentence did. So
the AC2 test registers the same address under each condition and asserts the rendered bodies are
byte-identical and the query counts equal, which is what "indistinguishable" has to mean.
"""
import re

import pytest
from django.contrib.auth.models import User
from django.core import mail
from django.core.cache import cache
from django.db import connection
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from jobradar.models import InviteCode, JobLead, UserProfile
from jobradar.services.email_verification import is_email_verified
from jobradar.services.prompt_builder import user_profile_settings

PASSWORD = 'quiet-harbour-42'
NEWCOMER = 'newcomer@example.test'


@pytest.fixture(autouse=True)
def _clear_throttle_history(db):
    """register_ip and email_verification_ip are cache-backed and every test here is 127.0.0.1."""
    cache.clear()


def register(email=NEWCOMER, friend=None, client=None):
    body = {'email': email, 'password': PASSWORD}
    if friend is not None:
        body['submit_for_username'] = friend
    return (client or APIClient()).post('/api/auth/register/', body, format='json')


def confirmation_link_parts():
    """(uid, token) from the newest confirmation email in the outbox."""
    match = re.search(r'/verify-email/([^/]+)/(\S+)', mail.outbox[-1].body)
    assert match, mail.outbox[-1].body
    return match.groups()


def confirm(uid, token):
    return APIClient().post('/api/auth/verify-email/', {'uid': uid, 'token': token}, format='json')


def register_and_confirm(email=NEWCOMER, friend=None):
    r = register(email, friend)
    assert r.status_code == 201, r.data
    uid, token = confirmation_link_parts()
    assert confirm(uid, token).status_code == 200
    return User.objects.get(username=email)


@override_settings(FRONTEND_URL='https://dachapply.example.test')
def test_registration_answers_byte_identically_whatever_friend_was_named(db):
    User.objects.create_user('friend@example.test', email='friend@example.test', password='pw')
    popular = User.objects.create_user('popular@example.test', email='popular@example.test', password='pw')
    suitor = User.objects.create_user('suitor@example.test', email='suitor@example.test', password='pw')
    UserProfile.objects.create(user=suitor, requested_submit_for=popular)

    named = {
        'exists': 'friend@example.test',
        'unknown': 'ghost@example.test',
        'own address': NEWCOMER,
        'exists and is already being asked by somebody else': 'popular@example.test',
        'not named at all': '',
    }
    # The first request of any test pays for rows the usage middleware creates once a day
    # (SiteDailyUsage and friends), which would otherwise show up as a three-query difference for
    # whichever case ran first and say nothing about registration. Measured: with this warm-up every
    # case costs the same 34 queries; without it the first one costs 37 whatever it is testing.
    register(email='warmup@example.test')
    answers = {}
    for label, friend in named.items():
        # Same registering address every time, so the only thing that varies between the responses
        # is the condition under test. Registration is the enumeration surface precisely because it
        # is anonymous, so the caller can always retry from a clean slate like this.
        User.objects.filter(username=NEWCOMER).delete()
        mail.outbox.clear()
        with CaptureQueriesContext(connection) as queries:
            response = register(friend=friend)
        response.render()
        answers[label] = (response.status_code, response.content, len(queries))

    assert len({answer[:2] for answer in answers.values()}) == 1, answers
    assert len({answer[2] for answer in answers.values()}) == 1, {k: v[2] for k, v in answers.items()}
    status, body, _queries = answers['exists']
    assert status == 201
    assert b'not found' not in body
    assert b'friend@example.test' not in body


def test_a_named_friend_is_only_linked_once_the_address_is_confirmed(db):
    friend = User.objects.create_user('linkme@example.test', email='linkme@example.test', password='pw')

    r = register(friend='linkme@example.test')
    assert r.status_code == 201
    assert r.data['requested_submit_for_username'] is None
    assert r.data['email_verified'] is False
    newcomer = User.objects.get(username=NEWCOMER)
    assert newcomer.jobradar_profile.requested_submit_for is None
    assert newcomer.jobradar_profile.pending_friend_lookup == 'linkme@example.test'
    # Nothing the friend can see yet, so an unconfirmed stranger cannot even spam the list.
    friend_client = APIClient()
    friend_client.force_authenticate(friend)
    assert friend_client.get('/api/auth/friend-requests/').data == []

    uid, token = confirmation_link_parts()
    assert confirm(uid, token).data == {'detail': 'Email address confirmed.'}

    newcomer.jobradar_profile.refresh_from_db()
    assert newcomer.jobradar_profile.email_verified is True
    assert newcomer.jobradar_profile.requested_submit_for == friend
    assert newcomer.jobradar_profile.pending_friend_lookup == ''
    assert friend_client.get('/api/auth/friend-requests/').data == [{'username': NEWCOMER}]


def test_an_unmatched_friend_name_is_dropped_in_silence_at_confirmation(db):
    newcomer = register_and_confirm(friend='ghost@example.test')
    profile = newcomer.jobradar_profile
    assert profile.email_verified is True
    assert profile.requested_submit_for is None
    assert profile.pending_friend_lookup == ''


def test_naming_yourself_as_the_friend_links_nothing(db):
    newcomer = register_and_confirm(friend=NEWCOMER)
    assert newcomer.jobradar_profile.requested_submit_for is None


def test_confirmation_link_survives_a_later_login_and_a_second_click(db):
    """The reason this feature does not reuse default_token_generator.

    Its hash covers last_login, and registration logs the account straight in, so a stock token
    would be dead before the user reached their inbox -- and dead again after the next login.
    """
    register()
    uid, token = confirmation_link_parts()
    client = APIClient()
    assert client.post('/api/auth/login/', {'username': NEWCOMER, 'password': PASSWORD}, format='json').status_code == 200
    assert confirm(uid, token).status_code == 200
    assert confirm(uid, token).status_code == 200
    assert User.objects.get(username=NEWCOMER).jobradar_profile.email_verified is True


def test_confirmation_rejects_a_tampered_token_and_a_junk_uid(db):
    register()
    uid, token = confirmation_link_parts()
    bad = confirm(uid, token[:-1] + ('a' if token[-1] != 'a' else 'b'))
    assert bad.status_code == 400 and bad.data['detail'] == 'Invalid or expired verification link'
    assert confirm('not-a-uid', token).status_code == 400
    assert User.objects.get(username=NEWCOMER).jobradar_profile.email_verified is False


def test_registration_survives_a_mail_host_that_is_down(db, monkeypatch):
    def fail_send_mail(*args, **kwargs):
        raise RuntimeError('SMTP unavailable')
    monkeypatch.setattr('jobradar.services.email_verification.send_mail', fail_send_mail)
    r = register()
    assert r.status_code == 201
    assert User.objects.filter(username=NEWCOMER).exists()
    assert mail.outbox == []


def test_unconfirmed_account_cannot_mint_an_invite_code(db):
    register()
    client = APIClient()
    client.force_authenticate(User.objects.get(username=NEWCOMER))
    r = client.post('/api/invites/', {'label': 'harvest'}, format='json')
    assert r.status_code == 403 and r.data['code'] == 'email_unverified'
    assert InviteCode.objects.count() == 0
    # Reading and revoking stay open: neither hands the caller anything new.
    assert client.get('/api/invites/').status_code == 200


def test_confirming_the_address_unlocks_invite_codes(db):
    newcomer = register_and_confirm()
    client = APIClient()
    client.force_authenticate(newcomer)
    r = client.post('/api/invites/', {'label': 'anna'}, format='json')
    assert r.status_code == 201
    assert InviteCode.objects.get(code=r.data['code']).owner == newcomer


def test_unconfirmed_account_cannot_approve_a_friend_request(db):
    register(email='host@example.test')
    host = User.objects.get(username='host@example.test')
    suitor = User.objects.create_user('suitor@example.test', email='suitor@example.test', password='pw')
    UserProfile.objects.create(user=suitor, requested_submit_for=host)

    client = APIClient()
    client.force_authenticate(host)
    r = client.post('/api/auth/friend-requests/', {'username': 'suitor@example.test'}, format='json')
    assert r.status_code == 403 and r.data['code'] == 'email_unverified'
    suitor.jobradar_profile.refresh_from_db()
    assert suitor.jobradar_profile.submit_for is None


def test_public_submit_waits_for_confirmation_when_a_friend_was_named(db):
    User.objects.create_user('host2@example.test', email='host2@example.test', password='pw')
    register(friend='host2@example.test')
    client = APIClient()
    client.force_authenticate(User.objects.get(username=NEWCOMER))
    r = client.post('/api/public/submit/', {'company': 'C', 'title': 'T', 'url': 'https://pending.test/1'}, format='json')
    assert r.status_code == 403
    # The job must not quietly land on the submitter's own board instead of the friend's.
    assert not JobLead.objects.filter(url__startswith='https://pending.test/').exists()


def test_accounts_that_predate_the_gate_are_verified(db):
    """AC3, both halves.

    Migration 0028 adds the column with default=True, which is the model default asserted on the
    profile below; accounts with no profile row at all -- the owner's, if onboarding was skipped,
    and every createsuperuser account -- have nothing for that default to land in and are read as
    verified by is_email_verified().
    """
    with_profile = User.objects.create_user('legacy@example.test', password='pw')
    profile = UserProfile.objects.create(user=with_profile, candidate_profile='LEGACY')
    assert profile.email_verified is True
    assert is_email_verified(with_profile) is True

    without_profile = User.objects.create_user('legacy-bare@example.test', password='pw')
    assert is_email_verified(without_profile) is True
    client = APIClient()
    client.force_authenticate(without_profile)
    assert client.get('/api/auth/me/').data['email_verified'] is True
    assert client.post('/api/invites/', {'label': 'still mine'}, format='json').status_code == 201

    # The trap: opening Settings get_or_create()s the profile row that was missing. It must not
    # arrive unverified and lock the account out of what it could do a moment earlier.
    assert user_profile_settings(without_profile).email_verified is True
    assert client.post('/api/invites/', {'label': 'after settings'}, format='json').status_code == 201


def test_resend_sends_a_fresh_link_only_while_unconfirmed(db):
    register()
    newcomer = User.objects.get(username=NEWCOMER)
    client = APIClient()
    client.force_authenticate(newcomer)
    mail.outbox.clear()

    r = client.post('/api/auth/verify-email/resend/', {}, format='json')
    assert r.status_code == 200
    assert len(mail.outbox) == 1
    assert mail.outbox[0].subject == 'Confirm your DACHApply email address'
    uid, token = confirmation_link_parts()
    assert confirm(uid, token).status_code == 200

    mail.outbox.clear()
    # Re-authenticating with a freshly loaded user is what the next real request does; the instance
    # pinned above still holds the jobradar_profile it cached before confirmation.
    client.force_authenticate(User.objects.get(username=NEWCOMER))
    r = client.post('/api/auth/verify-email/resend/', {}, format='json')
    assert r.status_code == 200 and r.data['detail'] == 'Your email address is already confirmed.'
    assert mail.outbox == []
