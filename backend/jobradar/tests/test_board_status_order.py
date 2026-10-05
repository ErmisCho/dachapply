"""TASK-267: the owner's dragged board status order -- UserProfile.board_status_order, the
JobLead.effective_status_order() helper, PATCH validation, /api/auth/me/ fields, and the default
board ordering following it."""
import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from jobradar.models import JobLead, UserProfile

ALL_STATUSES = [s for s, _label in JobLead.STATUSES]
DEFAULT = ['new', 'interview', 'reviewed', 'to_apply', 'ready_to_submit', 'applied', 'offer',
           'accepted', 'rejected', 'withdrawn', 'skipped', 'archived']


@pytest.fixture
def client(db):
    user = User.objects.create_user('order-owner', password='pw')
    c = APIClient(); c.force_authenticate(user); c.user = user; return c


def test_blank_order_is_the_task_145_default():
    assert JobLead.effective_status_order('') == DEFAULT
    assert JobLead.effective_status_order(None) == DEFAULT


def test_partial_order_appends_missing_statuses_in_default_order():
    order = JobLead.effective_status_order('ready_to_submit,applied')
    assert order == ['ready_to_submit', 'applied', *(s for s in DEFAULT if s not in ('ready_to_submit', 'applied'))]
    assert sorted(order) == sorted(ALL_STATUSES)


def test_unknown_and_duplicate_keys_are_dropped():
    assert JobLead.effective_status_order(' applied ,bogus,applied,new') == ['applied', 'new', *(s for s in DEFAULT if s not in ('applied', 'new'))]


def test_patch_rejects_unknown_status(client):
    r = client.patch('/api/profile/', {'board_status_order': 'new,bogus'}, format='json')
    assert r.status_code == 400 and 'board_status_order' in r.data
    assert UserProfile.objects.get(user=client.user).board_status_order == ''


def test_patch_normalizes_and_resets(client):
    assert client.get('/api/profile/').data['board_status_order'] == ''
    r = client.patch('/api/profile/', {'board_status_order': ' applied, new,,applied '}, format='json')
    assert r.status_code == 200 and r.data['board_status_order'] == 'applied,new'
    assert UserProfile.objects.get(user=client.user).board_status_order == 'applied,new'
    r = client.patch('/api/profile/', {'board_status_order': ''}, format='json')
    assert r.status_code == 200 and r.data['board_status_order'] == ''


def test_me_reports_effective_order_custom_flag_and_sort_keys(client):
    d = client.get('/api/auth/me/').data
    assert d['board_status_order'] == DEFAULT and d['board_status_order_custom'] is False and d['board_sort_keys'] == ''
    client.patch('/api/profile/', {'board_status_order': 'applied', 'board_sort_keys': 'status'}, format='json')
    d = client.get('/api/auth/me/').data
    assert d['board_status_order'][0] == 'applied' and len(d['board_status_order']) == len(ALL_STATUSES)
    assert d['board_status_order_custom'] is True and d['board_sort_keys'] == 'status'


def test_default_board_follows_the_saved_status_order(client):
    order = ['ready_to_submit', 'new', 'applied', 'interview']
    for s in reversed(order):  # created newest-last so -created_at alone would give the reverse
        JobLead.objects.create(created_by=client.user, company=s, title='role', status=s)
    UserProfile.objects.update_or_create(user=client.user, defaults={'board_status_order': ','.join(order)})
    r = client.get('/api/jobs/', {'status': ','.join(order)})
    assert r.status_code == 200 and [j['company'] for j in r.data] == order
    # An explicit ordering still wins over the status order.
    r = client.get('/api/jobs/', {'status': ','.join(order), 'ordering': 'status'})
    assert [j['company'] for j in r.data] == [s for s in ALL_STATUSES if s in order]
