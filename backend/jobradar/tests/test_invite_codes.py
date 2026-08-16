"""TASK-92: invite codes are owned, minted from the UI, and revocable.

The submission tests deliberately assert through the *recipient's* /api/jobs/ response rather
than through JobLead.submitted_for alone: "share a code with a friend" is only fixed if the
owner can actually read the job, so a future change to accessible_jobs() that drops
submitted_for access fails here instead of in production.
"""
import pytest
from django.contrib.auth.models import User
from django.core.cache import cache
from importlib import import_module
from rest_framework.test import APIClient

from jobradar.models import InviteCode, JobLead


@pytest.fixture(autouse=True)
def _clear_throttle_history(db):
    """public_submit keeps a 20/hour/IP throttle; every test here shares 127.0.0.1."""
    cache.clear()


@pytest.fixture
def recipient(db):
    return User.objects.create_user('recipient', password='pw')


@pytest.fixture
def recipient_client(recipient):
    c = APIClient()
    c.force_authenticate(recipient)
    return c


def mint(client, label=''):
    r = client.post('/api/invites/', {'label': label}, format='json')
    assert r.status_code == 201, r.data
    return r.data


def submit(code, url='https://friend.test/job', **extra):
    return APIClient().post('/api/public/submit/', {'invite_code': code, 'company': 'FriendCo', 'title': 'Referral', 'url': url, **extra}, format='json')


# AC1 -- anonymous submissions land on the code owner's dashboard.

def test_anonymous_submission_through_code_lands_on_the_owner_dashboard(recipient, recipient_client):
    code = mint(recipient_client, 'For Anna')['code']
    assert submit(code).status_code == 201
    job = JobLead.objects.get(url='https://friend.test/job')
    assert job.submitted_for == recipient and job.created_by is None
    assert [j['id'] for j in recipient_client.get('/api/jobs/').data] == [job.id]


def test_code_owner_owns_the_anonymous_submission_in_accessible_jobs(recipient, recipient_client):
    """The same claim as the test above, asserted one layer down.

    accessible_jobs() is the single definition of "on my dashboard" that every endpoint routes
    through, so this pins the ownership rule itself and keeps proving it while the /api/jobs/
    view is being changed by somebody else.
    """
    from jobradar.services.access import accessible_jobs
    assert submit(mint(recipient_client)['code']).status_code == 201
    job = JobLead.objects.get(url='https://friend.test/job')
    assert list(accessible_jobs(recipient)) == [job]
    assert list(accessible_jobs(User.objects.create_user('stranger', password='pw'))) == []


def test_anonymous_submission_is_invisible_to_other_users(recipient, recipient_client, db):
    code = mint(recipient_client)['code']
    assert submit(code).status_code == 201
    stranger = APIClient()
    stranger.force_authenticate(User.objects.create_user('stranger', password='pw'))
    assert stranger.get('/api/jobs/').data == []


def test_legacy_ownerless_code_still_accepts_submissions(db):
    """Pre-TASK-92 rows have owner=None. They must keep working, unowned as before."""
    InviteCode.objects.create(code='LEGACY')
    assert submit('LEGACY').status_code == 201
    assert JobLead.objects.get(url='https://friend.test/job').submitted_for is None


# AC2 -- mint and revoke, with generated code values.

def test_minted_code_is_generated_and_not_taken_from_the_request(recipient_client):
    r = recipient_client.post('/api/invites/', {'label': 'For Bob', 'code': 'CHOSEN-BY-ME'}, format='json')
    assert r.status_code == 201
    assert r.data['code'] != 'CHOSEN-BY-ME' and len(r.data['code']) >= 12
    assert r.data['label'] == 'For Bob' and r.data['active'] is True


def test_minting_twice_yields_distinct_codes(recipient_client):
    assert mint(recipient_client)['code'] != mint(recipient_client)['code']


def test_invite_list_is_scoped_to_the_owner(recipient, recipient_client, db):
    mine = mint(recipient_client)['code']
    other = APIClient()
    other.force_authenticate(User.objects.create_user('other', password='pw'))
    theirs = mint(other)['code']
    assert [c['code'] for c in recipient_client.get('/api/invites/').data] == [mine]
    assert other.delete(f'/api/invites/{InviteCode.objects.get(code=mine).id}/').status_code == 404
    assert InviteCode.objects.get(code=mine).active is True and theirs


def test_invites_require_authentication(db):
    assert APIClient().get('/api/invites/').status_code == 403


# AC4 -- revocation stops new submissions without touching history.

def test_revoking_a_code_blocks_new_submissions_but_keeps_the_jobs(recipient, recipient_client):
    invite = mint(recipient_client)
    assert submit(invite['code'], url='https://friend.test/before').status_code == 201
    assert recipient_client.delete(f"/api/invites/{invite['id']}/").status_code == 204

    assert submit(invite['code'], url='https://friend.test/after').status_code == 400
    assert not JobLead.objects.filter(url='https://friend.test/after').exists()

    assert InviteCode.objects.filter(pk=invite['id'], active=False).exists(), 'revoke must soft-flip, not delete the audit row'
    kept = JobLead.objects.get(url='https://friend.test/before')
    assert kept.submitted_for == recipient
    assert kept.id in [j['id'] for j in recipient_client.get('/api/jobs/').data]


def test_expired_code_is_rejected(recipient, recipient_client):
    from django.utils import timezone
    invite = mint(recipient_client)
    InviteCode.objects.filter(pk=invite['id']).update(expires_at=timezone.now() - timezone.timedelta(days=1))
    assert submit(invite['code']).status_code == 400


# AC3 -- existing codes migrate to the current owner.

def _backfill():
    from django.apps import apps
    module = import_module('jobradar.migrations.0026_alter_invitecode_options_invitecode_owner')
    module.assign_existing_codes(apps, None)


def test_backfill_assigns_existing_codes_to_the_first_superuser(db):
    User.objects.create_user('regular', password='pw')
    admin = User.objects.create_superuser('admin', password='pw')
    User.objects.create_superuser('later-admin', password='pw')
    InviteCode.objects.create(code='OLD-1')
    InviteCode.objects.create(code='OLD-2')
    _backfill()
    assert set(InviteCode.objects.values_list('owner', flat=True)) == {admin.id}


def test_backfill_falls_back_to_staff_and_never_picks_a_plain_user(db):
    User.objects.create_user('regular', password='pw')
    staff = User.objects.create_user('staff', password='pw', is_staff=True)
    InviteCode.objects.create(code='OLD')
    _backfill()
    assert InviteCode.objects.get(code='OLD').owner == staff


def test_backfill_is_a_noop_on_a_database_with_no_admin_users(db):
    """CI and any fresh checkout run this migration with an empty auth_user table."""
    InviteCode.objects.create(code='OLD')
    _backfill()
    assert InviteCode.objects.get(code='OLD').owner is None
    User.objects.create_user('regular', password='pw')
    _backfill()
    assert InviteCode.objects.get(code='OLD').owner is None


def test_backfill_does_not_reassign_an_already_owned_code(recipient):
    User.objects.create_superuser('admin', password='pw')
    InviteCode.objects.create(code='MINE', owner=recipient)
    _backfill()
    assert InviteCode.objects.get(code='MINE').owner == recipient
