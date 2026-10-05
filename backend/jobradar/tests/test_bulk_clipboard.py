"""TASK-261: bulk generation opts out of per-task clipboard writes and copies once via its own endpoint.

Hermetic: start_cv_task and copy_text_to_clipboard are replaced, so no provider runs and the real
OS clipboard is never touched.
"""
import pytest
from django.conf import settings
from django.contrib.auth.models import User
from django.test import override_settings
from rest_framework.test import APIClient

from jobradar.models import JobLead, UserProfile

OWNER = override_settings(CODEX_CV_ENABLED=True, CODEX_CV_OWNER_EMAIL='owner@example.test',
                          REST_FRAMEWORK={**settings.REST_FRAMEWORK, 'DEFAULT_THROTTLE_RATES': {
                              **settings.REST_FRAMEWORK.get('DEFAULT_THROTTLE_RATES', {}), 'cv_generation_user': '100/hour'}})


@pytest.fixture
def owner(db):
    user = User.objects.create_user('owner', email='owner@example.test', password='pw')
    UserProfile.objects.create(user=user, candidate_profile='backend engineer')
    return user


@pytest.fixture
def client(owner):
    c = APIClient(); c.force_authenticate(owner); return c


@pytest.fixture
def started(owner, monkeypatch):
    calls = []
    monkeypatch.setattr('jobradar.views.validate_model_capability', lambda *a, **k: None)
    monkeypatch.setattr('jobradar.views.load_candidate_evidence', lambda *a: 'profile')
    monkeypatch.setattr('jobradar.views.start_cv_task', lambda *a, **k: calls.append(k) or 'task123')
    return calls


PAYLOAD = {'cv_template': 'de', 'letter_template': 'anschreiben', 'provider': 'openai', 'model': 'gpt-5.5', 'effort': 'medium'}


@OWNER
def test_bulk_generation_disables_per_task_clipboard_and_single_job_keeps_it(client, owner, started):
    job = JobLead.objects.create(company='ACME', title='Python Engineer', created_by=owner)
    assert client.post(f'/api/jobs/{job.id}/cv-generation/run/', {**PAYLOAD, 'auto_clipboard': False}, format='json').status_code == 202
    assert client.post(f'/api/jobs/{job.id}/cv-generation/run/', PAYLOAD, format='json').status_code == 202
    assert started == [{'create_cv': True, 'auto_clipboard': False}, {'create_cv': True}]


@OWNER
def test_clipboard_endpoint_copies_text_on_the_server(client, monkeypatch):
    copied = []
    monkeypatch.setattr('jobradar.services.cv_tasks.copy_text_to_clipboard', lambda text: copied.append(text) or True)
    r = client.post('/api/cv-generation/clipboard/', {'text': '% Job listing: x\n\nCV'}, format='json')
    assert r.status_code == 200 and r.data == {'copied': True} and copied == ['% Job listing: x\n\nCV']
    monkeypatch.setattr('jobradar.services.cv_tasks.copy_text_to_clipboard', lambda text: False)
    assert client.post('/api/cv-generation/clipboard/', {'text': 'CV'}, format='json').data == {'copied': False}


@OWNER
def test_clipboard_endpoint_rejects_empty_text_and_non_owners(client, db, monkeypatch):
    copied = []
    monkeypatch.setattr('jobradar.services.cv_tasks.copy_text_to_clipboard', lambda text: copied.append(text) or True)
    assert client.post('/api/cv-generation/clipboard/', {'text': '  '}, format='json').status_code == 400
    assert client.post('/api/cv-generation/clipboard/', {}, format='json').status_code == 400
    stranger = APIClient(); stranger.force_authenticate(User.objects.create_user('stranger', email='s@example.test'))
    assert stranger.post('/api/cv-generation/clipboard/', {'text': 'CV'}, format='json').status_code == 404
    assert copied == []
