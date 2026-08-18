"""TASK-117 (API half): the per-job mailbox endpoint, the unmatched-mail list, manual attach, and
the confirm-records-who-confirmed change. Fixture conventions mirror test_mailbox.py (same
_isolated_mailbox_env autouse fixture, owner/client, applied_job, _log_message) -- no factory
library, plain objects.create.
"""
import pytest
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APIClient

from jobradar.models import JobLead, MailboxDraft, MailboxMessage, MailboxRun, MailboxSuggestion
from jobradar.services.prompt_builder import user_profile_settings


@pytest.fixture(autouse=True)
def _isolated_mailbox_env(settings):
    """Same isolation as test_mailbox.py's fixture of the same name -- a developer machine
    configured with real Gmail/CV-owner settings must not change what these tests exercise.
    """
    settings.GMAIL_IMAP_HOST = 'imap.gmail.com'
    settings.GMAIL_IMAP_USER = 'owner@example.test'
    settings.GMAIL_IMAP_APP_PASSWORD = 'fake-app-password'
    settings.GMAIL_CALENDAR_ICS_URL = ''
    settings.CODEX_CV_ENABLED = True
    settings.CODEX_CV_OWNER_EMAIL = 'owner@example.test'
    settings.MAILBOX_SALARY_FLOOR_EUR = ''
    settings.MAILBOX_DO_NOT_DISCLOSE = []


@pytest.fixture
def owner(db):
    user = User.objects.create_user('owner@example.test', email='owner@example.test', password='pw')
    user_profile_settings(user)  # creates the UserProfile row with real model defaults
    return user


@pytest.fixture
def client(db, owner):
    c = APIClient()
    c.force_authenticate(owner)
    c.user = owner
    return c


@pytest.fixture
def applied_job(db, owner):
    return JobLead.objects.create(company='Acme', title='Engineer', url='https://acme.test/1', status='applied', status_date=timezone.localdate(), created_by=owner)


def _log_message(job, classification='uncertain', sender='hr@acme.test', subject='x', body_text=''):
    run = MailboxRun.objects.create()
    return MailboxMessage.objects.create(run=run, uid=MailboxMessage.objects.count() + 1, sender=sender, subject=subject, body_text=body_text, classification=classification, matched_job=job)


# --- AC2: per-job mailbox endpoint --------------------------------------------------------------

def test_job_mailbox_endpoint_returns_messages_with_body_draft_and_pending_suggestions(client, applied_job):
    message = _log_message(applied_job, 'interview_invitation', body_text='Sehr geehrter Herr Chorinopoulos, ...')
    MailboxDraft.objects.create(message=message, job=applied_job, status='written', subject='Re: x', body_text='Vielen Dank...', evaluator='template')
    pending = MailboxSuggestion.objects.create(message=message, job=applied_job, suggestion_type='interview_date', payload={'interview_at': None})
    decided = MailboxSuggestion.objects.create(message=message, job=applied_job, suggestion_type='feedback_clear', payload={'feedback_due_date': None}, status='confirmed', decided_at=timezone.now())

    r = client.get(f'/api/jobs/{applied_job.id}/mailbox/')

    assert r.status_code == 200
    assert len(r.data) == 1
    row = r.data[0]
    assert row['id'] == message.id
    assert row['body_text'] == 'Sehr geehrter Herr Chorinopoulos, ...'
    assert row['draft']['body_text'] == 'Vielen Dank...'
    suggestion_ids = [s['id'] for s in row['suggestions']]
    assert pending.id in suggestion_ids
    assert decided.id not in suggestion_ids


def test_job_mailbox_endpoint_orders_newest_first(client, applied_job):
    older = _log_message(applied_job, 'uncertain')
    newer = _log_message(applied_job, 'uncertain')
    r = client.get(f'/api/jobs/{applied_job.id}/mailbox/')
    assert [row['id'] for row in r.data] == [newer.id, older.id]


def test_job_mailbox_endpoint_for_inaccessible_job_is_404_with_no_body_leaked(db, applied_job):
    """AC2/AC7: a second user asking for someone else's job gets a 404, not a body -- asserted on
    the real HTTP response, not the serializer.
    """
    _log_message(applied_job, 'rejection', body_text='very private salary and rejection details')
    other = User.objects.create_user('other@example.test', email='other@example.test', password='pw')
    other_client = APIClient(); other_client.force_authenticate(other)

    r = other_client.get(f'/api/jobs/{applied_job.id}/mailbox/')

    assert r.status_code == 404
    assert 'very private salary and rejection details' not in r.content.decode('utf-8')


# --- AC6: unmatched list -------------------------------------------------------------------------

def test_unmatched_messages_list_is_empty_for_non_owner_and_populated_for_owner(client, applied_job):
    unmatched = _log_message(None, 'uncertain', sender='hr@agency.test', body_text='We are recruiting for a role like yours.')
    matched = _log_message(applied_job, 'rejection')
    not_job_related = _log_message(None, 'not_job_related', sender='news@random.test')

    other = User.objects.create_user('other4@example.test', email='other4@example.test', password='pw')
    other_client = APIClient(); other_client.force_authenticate(other)

    owner_response = client.get('/api/mailbox-messages/unmatched/')
    other_response = other_client.get('/api/mailbox-messages/unmatched/')

    assert other_response.data == []
    ids = [row['id'] for row in owner_response.data]
    assert unmatched.id in ids
    assert matched.id not in ids  # already matched -- not "unmatched"
    assert not_job_related.id not in ids  # not job-related -- not something to review
    assert owner_response.data[0]['body_text'] == 'We are recruiting for a role like yours.'


# --- AC6: attach ----------------------------------------------------------------------------------

def test_attach_sets_matched_job_and_produces_same_suggestions_as_domain_match(client, owner):
    job = JobLead.objects.create(company='Acme', title='Engineer', url='https://acme.test/1', status='applied', status_date=timezone.localdate(), created_by=owner)
    # Sender domain matches nothing tracked -- an agency or personal address.
    message = _log_message(None, 'rejection', sender='someone@totally-unrelated-agency.test')
    assert message.matched_job_id is None

    r = client.post(f'/api/mailbox-messages/{message.id}/attach/', {'job': job.id}, format='json')

    assert r.status_code == 200
    message.refresh_from_db()
    assert message.matched_job_id == job.id
    suggestion_ids = [s['id'] for s in r.data['suggestions']]
    domain_matched_suggestion = MailboxSuggestion.objects.get(message__sender='someone@totally-unrelated-agency.test', job=job)
    assert domain_matched_suggestion.suggestion_type == 'status_change'
    assert domain_matched_suggestion.payload == {'status': 'rejected'}
    assert domain_matched_suggestion.id in suggestion_ids


def test_attach_to_a_job_the_user_cannot_see_is_404(client):
    other = User.objects.create_user('other5@example.test', email='other5@example.test', password='pw')
    someone_elses_job = JobLead.objects.create(company='Other Co', title='Role', created_by=other)
    message = _log_message(None, 'uncertain', sender='someone@agency.test')

    r = client.post(f'/api/mailbox-messages/{message.id}/attach/', {'job': someone_elses_job.id}, format='json')

    assert r.status_code == 404
    message.refresh_from_db()
    assert message.matched_job_id is None


def test_reattaching_to_a_different_job_is_rejected(client, owner):
    first_job = JobLead.objects.create(company='Acme', title='Engineer', created_by=owner)
    second_job = JobLead.objects.create(company='Globex', title='Manager', created_by=owner)
    message = _log_message(first_job, 'uncertain', sender='someone@agency.test')

    r = client.post(f'/api/mailbox-messages/{message.id}/attach/', {'job': second_job.id}, format='json')

    assert r.status_code == 400
    message.refresh_from_db()
    assert message.matched_job_id == first_job.id


def test_reattaching_to_the_same_job_is_a_harmless_noop(client, owner):
    job = JobLead.objects.create(company='Acme', title='Engineer', status='applied', status_date=timezone.localdate(), created_by=owner)
    message = _log_message(job, 'rejection', sender='someone@agency.test')
    MailboxSuggestion.objects.create(message=message, job=job, suggestion_type='status_change', payload={'status': 'rejected'})

    r = client.post(f'/api/mailbox-messages/{message.id}/attach/', {'job': job.id}, format='json')

    assert r.status_code == 200
    assert MailboxSuggestion.objects.filter(message=message, job=job).count() == 1  # not duplicated


def test_attach_requires_cv_owner(db, applied_job):
    other = User.objects.create_user('other6@example.test', email='other6@example.test', password='pw')
    other_client = APIClient(); other_client.force_authenticate(other)
    message = _log_message(None, 'uncertain', sender='someone@agency.test')

    r = other_client.post(f'/api/mailbox-messages/{message.id}/attach/', {'job': applied_job.id}, format='json')

    assert r.status_code == 404
    message.refresh_from_db()
    assert message.matched_job_id is None


# --- AC4: confirm records who confirmed -----------------------------------------------------------

def test_confirm_passes_the_confirming_user_through(client, owner, applied_job):
    message = _log_message(applied_job, 'rejection')
    suggestion = MailboxSuggestion.objects.create(message=message, job=applied_job, suggestion_type='status_change', payload={'status': 'rejected'})

    r = client.post(f'/api/mailbox-suggestions/{suggestion.id}/confirm/')

    assert r.status_code == 200
    note = applied_job.notes.get(note_type='recruiter_message')
    assert note.created_by_id == owner.id


# --- AC7: /api/mailbox-runs/ regression guard -----------------------------------------------------

def test_mailbox_runs_still_owner_gated(db, owner):
    MailboxRun.objects.create(fetched_count=1)
    other = User.objects.create_user('other7@example.test', email='other7@example.test', password='pw')
    owner_client = APIClient(); owner_client.force_authenticate(owner)
    other_client = APIClient(); other_client.force_authenticate(other)

    assert len(owner_client.get('/api/mailbox-runs/').data) == 1
    assert other_client.get('/api/mailbox-runs/').data == []
