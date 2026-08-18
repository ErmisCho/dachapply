"""TASK-117 (API half): the per-job mailbox endpoint, the unmatched-mail list, manual attach, and
the confirm-records-who-confirmed change. Fixture conventions mirror test_mailbox.py (same
_isolated_mailbox_env autouse fixture, owner/client, applied_job, _log_message) -- no factory
library, plain objects.create.
"""
import pytest
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APIClient

from jobradar.models import ApplicationNote, JobLead, MailboxDraft, MailboxMessage, MailboxRun, MailboxSuggestion
from jobradar.services import mailbox
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


def _log_message(job, classification='uncertain', sender='hr@acme.test', subject='x', body_text='', message_id='', received_at=None):
    run = MailboxRun.objects.create()
    return MailboxMessage.objects.create(run=run, uid=MailboxMessage.objects.count() + 1, sender=sender, subject=subject, body_text=body_text, classification=classification, matched_job=job, message_id=message_id, received_at=received_at)


# --- AC2: per-job mailbox endpoint --------------------------------------------------------------

def test_job_mailbox_endpoint_returns_messages_with_body_draft_and_pending_suggestions(client, applied_job):
    message = _log_message(applied_job, 'interview_invitation', body_text='Sehr geehrter Herr Chorinopoulos, ...')
    MailboxDraft.objects.create(message=message, job=applied_job, status='written', subject='Re: x', body_text='Vielen Dank...', evaluator='template')
    pending = MailboxSuggestion.objects.create(message=message, job=applied_job, suggestion_type='interview_date', payload={'interview_at': None})
    decided = MailboxSuggestion.objects.create(message=message, job=applied_job, suggestion_type='feedback_clear', payload={'feedback_due_date': None}, status='confirmed', decided_at=timezone.now())

    r = client.get(f'/api/jobs/{applied_job.id}/mailbox/')

    assert r.status_code == 200
    assert len(r.data['messages']) == 1
    row = r.data['messages'][0]
    assert row['id'] == message.id
    assert row['body_text'] == 'Sehr geehrter Herr Chorinopoulos, ...'
    assert row['draft']['body_text'] == 'Vielen Dank...'
    suggestion_ids = [s['id'] for s in row['suggestions']]
    assert pending.id in suggestion_ids
    assert decided.id not in suggestion_ids


def test_job_mailbox_endpoint_orders_by_received_at_not_uid(client, applied_job):
    """TASK-120 AC2: uid is a locally-assigned sequence number for Gmail-API rows, not a received
    time (see MailboxMessage's docstring) -- the message logged SECOND (higher uid) but received
    EARLIER must still sort after the one logged FIRST but received LATER.
    """
    now = timezone.now()
    logged_first_received_later = _log_message(applied_job, 'uncertain', received_at=now)
    logged_second_received_earlier = _log_message(applied_job, 'uncertain', received_at=now - timezone.timedelta(days=1))

    r = client.get(f'/api/jobs/{applied_job.id}/mailbox/')

    assert [row['id'] for row in r.data['messages']] == [logged_first_received_later.id, logged_second_received_earlier.id]


def test_job_mailbox_endpoint_puts_null_received_at_last(client, applied_job):
    """TASK-120 AC2: received_at is nullable -- nulls sort last (deliberately, see the view's
    comment), never interleaved arbitrarily among dated rows.
    """
    dated = _log_message(applied_job, 'uncertain', received_at=timezone.now())
    undated = _log_message(applied_job, 'uncertain', received_at=None)

    r = client.get(f'/api/jobs/{applied_job.id}/mailbox/')

    assert [row['id'] for row in r.data['messages']] == [dated.id, undated.id]


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


# --- TASK-126 AC1/AC4: has_mailbox_history on /api/jobs/ (the board's list) -----------------------
# The bug: the board used to derive "this job has mail" only from /mailbox-suggestions/, which is
# pending-only by default, so a job whose one suggestion was already decided showed no indicator at
# all even though TASK-120's history/notes view still had something to show. has_mailbox_history is
# the recorded fix (option 1 in the task notes): an Exists() annotation on the list queryset itself,
# true the moment ANY MailboxMessage is matched to the job, regardless of what its suggestions (if
# any) decided to.

def test_jobs_list_flags_has_mailbox_history_for_a_job_with_a_pending_suggestion(client, applied_job):
    message = _log_message(applied_job, 'interview_invitation')
    MailboxSuggestion.objects.create(message=message, job=applied_job, suggestion_type='interview_date', payload={})

    r = client.get('/api/jobs/')

    row = next(j for j in r.data if j['id'] == applied_job.id)
    assert row['has_mailbox_history'] is True


def test_jobs_list_flags_has_mailbox_history_for_a_job_whose_only_suggestion_is_decided(client, applied_job):
    """The exact bug: a suggestion that has already been confirmed/dismissed must not make the
    job's mail history invisible again -- that decided suggestion still came with a message.
    """
    message = _log_message(applied_job, 'rejection')
    MailboxSuggestion.objects.create(message=message, job=applied_job, suggestion_type='status_change', payload={'status': 'rejected'}, status='confirmed', decided_at=timezone.now())

    r = client.get('/api/jobs/')

    row = next(j for j in r.data if j['id'] == applied_job.id)
    assert row['has_mailbox_history'] is True


def test_jobs_list_has_mailbox_history_false_for_a_job_with_no_mail_at_all(client, applied_job):
    r = client.get('/api/jobs/')

    row = next(j for j in r.data if j['id'] == applied_job.id)
    assert row['has_mailbox_history'] is False


# --- TASK-120 AC3/AC4: the job's notes travel with its mail in the same response -------------------

def test_job_mailbox_endpoint_includes_the_jobs_notes_newest_first_with_their_type(client, applied_job):
    _log_message(applied_job, 'uncertain')  # notes must appear even with no messages driving them
    older = ApplicationNote.objects.create(job=applied_job, note='Called to follow up', note_type='follow_up')
    newer = ApplicationNote.objects.create(job=applied_job, note='Confirmed: moved to rejected because they replied "no fit"', note_type='recruiter_message')

    r = client.get(f'/api/jobs/{applied_job.id}/mailbox/')

    assert r.status_code == 200
    assert [n['id'] for n in r.data['notes']] == [newer.id, older.id]  # newest first
    assert r.data['notes'][0]['note_type'] == 'recruiter_message'
    assert r.data['notes'][1]['note_type'] == 'follow_up'


def test_job_mailbox_endpoint_notes_of_an_inaccessible_job_are_not_leaked(db, applied_job):
    ApplicationNote.objects.create(job=applied_job, note='very private note', note_type='general')
    other = User.objects.create_user('other9@example.test', email='other9@example.test', password='pw')
    other_client = APIClient(); other_client.force_authenticate(other)

    r = other_client.get(f'/api/jobs/{applied_job.id}/mailbox/')

    assert r.status_code == 404
    assert 'very private note' not in r.content.decode('utf-8')


# --- TASK-121 AC3/AC4: the Gmail link, exposed by the server so the client never builds one --------

def test_job_mailbox_endpoint_message_gmail_url_is_null_without_a_usable_id(client, applied_job):
    message = _log_message(applied_job, 'uncertain')  # message_id='' by default

    r = client.get(f'/api/jobs/{applied_job.id}/mailbox/')

    row = next(m for m in r.data['messages'] if m['id'] == message.id)
    assert row['gmail_url'] is None


def test_job_mailbox_endpoint_message_gmail_url_is_built_from_the_message_id(client, applied_job):
    message = _log_message(applied_job, 'uncertain', message_id='<abc123@mail.gmail.com>')

    r = client.get(f'/api/jobs/{applied_job.id}/mailbox/')

    row = next(m for m in r.data['messages'] if m['id'] == message.id)
    assert row['gmail_url'] == mailbox.gmail_conversation_url('<abc123@mail.gmail.com>', authuser=mailbox._reply_from_address() or '')
    assert 'rfc822msgid:abc123' in row['gmail_url']


def test_job_mailbox_endpoint_gmail_url_names_the_account_it_means(client, applied_job, settings):
    """TASK-121 AC3, measured in the owner's real browser 2026-08-18 and then regression-guarded.

    A bare /mail/u/0/#search/... opens whichever Google account signed in FIRST in that browser. The
    owner's mailbox was account index 3, so the first link found nothing until /u/0/ was hand-edited
    to /u/3/. Passing the mailbox's own address as authuser makes Gmail resolve the account itself
    (confirmed: it redirected to /mail/u/3/ and found the message). Without this the link is a
    coin flip on any machine signed into more than one Google account.
    """
    settings.GMAIL_IMAP_USER = 'owner@example.test'
    message = _log_message(applied_job, 'uncertain', message_id='<acct@mail.gmail.com>')

    r = client.get(f'/api/jobs/{applied_job.id}/mailbox/')

    url = next(m for m in r.data['messages'] if m['id'] == message.id)['gmail_url']
    assert 'authuser=owner%40example.test' in url, 'the link must say which account it means'
    assert url.index('authuser=') < url.index('#'), 'authuser is a query param, not part of the fragment'


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


# --- TASK-122 AC1: editing a draft's text ----------------------------------------------------------

def _written_draft(job, message, **extra):
    defaults = dict(status='written', subject='Re: x', body_text='old text', evaluator='template', gmail_draft_id='draft-1', gmail_message_id='msg-1', gmail_thread_id='thread-1')
    defaults.update(extra)
    return MailboxDraft.objects.create(message=message, job=job, **defaults)


def _fake_gmail_transport(monkeypatch, calls):
    """A real GmailApiTransport instance (never touches a socket -- __init__ only stores attrs) with
    update_draft replaced, wired in as the module's _default_transport() so update_draft_text's
    isinstance(transport, GmailApiTransport) check passes.
    """
    transport = mailbox.GmailApiTransport('cid', 'secret', 'unused-token-path')
    monkeypatch.setattr(transport, 'update_draft', lambda draft_id, mime_message, thread_id=None: calls.append((draft_id, thread_id)))
    monkeypatch.setattr(mailbox, '_default_transport', lambda: transport)
    return transport


def test_edit_draft_action_updates_gmail_and_database_and_marks_evaluator_human(client, applied_job, monkeypatch):
    message = _log_message(applied_job, 'interview_invitation')
    draft = _written_draft(applied_job, message)
    calls = []
    _fake_gmail_transport(monkeypatch, calls)

    r = client.post(f'/api/mailbox-drafts/{draft.id}/edit/', {'body_text': 'new text'}, format='json')

    assert r.status_code == 200
    assert r.data['body_text'] == 'new text'
    draft.refresh_from_db()
    assert draft.body_text == 'new text'
    assert draft.evaluator == 'human'
    assert calls == [('draft-1', 'thread-1')]  # updated in Gmail, not only the database


def test_edit_draft_action_refuses_on_guardrail_failure_and_leaves_draft_unchanged(client, owner, applied_job, monkeypatch):
    message = _log_message(applied_job, 'interview_invitation')
    draft = _written_draft(applied_job, message)
    profile = user_profile_settings(owner)
    profile.mailbox_do_not_disclose = 'my current salary'
    profile.save()
    calls = []
    _fake_gmail_transport(monkeypatch, calls)

    r = client.post(f'/api/mailbox-drafts/{draft.id}/edit/', {'body_text': 'Happy to share that my current salary is great.'}, format='json')

    assert r.status_code == 400
    assert 'current salary' in r.data['detail']
    draft.refresh_from_db()
    assert draft.body_text == 'old text'
    assert draft.evaluator == 'template'
    assert calls == []  # nothing written to Gmail on a refusal


def test_edit_draft_action_for_a_job_the_user_cannot_see_is_404(client, applied_job, monkeypatch):
    message = _log_message(applied_job, 'interview_invitation')
    draft = _written_draft(applied_job, message)
    calls = []
    _fake_gmail_transport(monkeypatch, calls)
    other = User.objects.create_user('other10@example.test', email='other10@example.test', password='pw')
    other_client = APIClient(); other_client.force_authenticate(other)

    r = other_client.post(f'/api/mailbox-drafts/{draft.id}/edit/', {'body_text': 'sneaky edit'}, format='json')

    assert r.status_code == 404
    draft.refresh_from_db()
    assert draft.body_text == 'old text'
    assert calls == []


# --- TASK-88 AC2: the deliberate-error endpoint that proves alerting works ------------------------

def test_raise_test_error_is_owner_gated_and_does_not_leak_its_existence(db):
    """A deliberate-500 endpoint is a liability if anyone can reach it: every hit mails the owner,
    so an open one is both an alert-spam vector and a way to burn the Brevo quota that password-reset
    mail depends on. Non-owners get 404 (not 403), so the endpoint does not advertise itself.
    """
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient

    other = get_user_model().objects.create_user('stranger@example.test', email='stranger@example.test', password='pw')
    client = APIClient()
    client.force_authenticate(other)

    r = client.post('/api/debug/raise-test-error/')

    assert r.status_code == 404, 'a non-owner must not be able to trigger an alert'


def test_raise_test_error_actually_raises_for_the_owner(client, owner, settings):
    """The whole point: it must genuinely raise so Django's django.request logger fires the
    AdminEmailHandler. A view that returned 500 without raising would test nothing.
    """
    import pytest
    settings.CODEX_CV_OWNER_EMAIL = owner.email

    with pytest.raises(RuntimeError, match='TASK-88 AC2'):
        client.post('/api/debug/raise-test-error/')


# --- TASK-125 AC1/AC2: the settings surface round-trips through /api/profile/ ----------------------

def test_mailbox_check_enabled_and_window_round_trip_through_profile_settings(client):
    payload = {'mailbox_check_enabled': False, 'mailbox_check_window_start': '22:00:00', 'mailbox_check_window_end': '06:00:00'}

    r = client.patch('/api/profile/', payload, format='json')
    assert r.status_code == 200
    assert r.data['mailbox_check_enabled'] is False
    assert r.data['mailbox_check_window_start'] == '22:00:00'
    assert r.data['mailbox_check_window_end'] == '06:00:00'

    r = client.get('/api/profile/')
    assert r.data['mailbox_check_enabled'] is False
    assert r.data['mailbox_check_window_start'] == '22:00:00'
    assert r.data['mailbox_check_window_end'] == '06:00:00'


# --- TASK-124 AC1/AC2/AC9: the manual "run now" trigger --------------------------------------------

def test_run_now_starts_a_background_run_and_returns_immediately(client, monkeypatch):
    """AC1: verified against a run slower than a normal request timeout -- the HTTP response must
    come back long before the (stubbed) run finishes, not after."""
    import time

    from jobradar.services import mailbox_tasks

    def slow_run_check(force=False, transport=None):
        time.sleep(0.5)
        return None  # no DB write from the background thread -- see the test's own note below

    monkeypatch.setattr(mailbox_tasks, 'run_check', slow_run_check)

    started = time.monotonic()
    r = client.post('/api/mailbox-runs/run-now/')
    elapsed = time.monotonic() - started

    assert r.status_code == 200
    assert r.data['queued'] is False
    assert 'task_id' in r.data
    assert elapsed < 0.4, 'the request must return before the slow run finishes, not block on it'


def test_run_now_queues_a_request_when_this_backend_has_no_credentials(client, owner, settings):
    """AC2: the deployed-site path -- no GMAIL_* configured, so a request is recorded instead of a
    run being started, and nothing is silently dropped."""
    settings.GMAIL_IMAP_USER = ''
    settings.GMAIL_IMAP_APP_PASSWORD = ''

    r = client.post('/api/mailbox-runs/run-now/')

    assert r.status_code == 200
    assert r.data['queued'] is True
    assert 'request_id' in r.data
    from jobradar.models import MailboxCheckRequest
    request = MailboxCheckRequest.objects.get(pk=r.data['request_id'])
    assert request.requested_by_id == owner.id
    assert request.handled_at is None


def test_run_now_requires_cv_owner(db, applied_job):
    other = User.objects.create_user('other11@example.test', email='other11@example.test', password='pw')
    other_client = APIClient(); other_client.force_authenticate(other)

    r = other_client.post('/api/mailbox-runs/run-now/')

    assert r.status_code == 404


# --- TASK-124 AC5/AC6/AC7/AC8: the pollable status + estimate endpoint -----------------------------

def test_mailbox_run_status_endpoint_shape_with_no_history(client):
    r = client.get('/api/mailbox-runs/status/')

    assert r.status_code == 200
    assert r.data['has_credentials'] is True  # fixture configures GMAIL_IMAP_USER/APP_PASSWORD
    assert r.data['running'] is False
    assert r.data['run'] is None
    assert r.data['estimate'] == {'kind': 'cold', 'estimated_seconds': None}
    assert r.data['elapsed_seconds'] is None
    assert r.data['taking_longer_than_usual'] is False


def test_mailbox_run_status_endpoint_reports_live_progress_while_running(client):
    run = MailboxRun.objects.create(fetched_count=5)
    MailboxRun.objects.filter(pk=run.pk).update(started_at=timezone.now() - timezone.timedelta(seconds=10))

    r = client.get('/api/mailbox-runs/status/')

    assert r.status_code == 200
    assert r.data['running'] is True
    assert r.data['run']['id'] == run.id
    assert r.data['run']['fetched_count'] == 5
    assert r.data['elapsed_seconds'] >= 10


def test_mailbox_run_status_endpoint_says_taking_longer_than_usual_past_the_estimate(client, applied_job):
    completed = MailboxRun.objects.create(drafting_skipped=False)
    MailboxRun.objects.filter(pk=completed.pk).update(
        started_at=timezone.now() - timezone.timedelta(seconds=10),
        finished_at=timezone.now() - timezone.timedelta(seconds=5),
    )
    # A message exists (attached to the already-FINISHED run above), so the NEXT check is
    # incremental, not cold -- attaching to `completed` rather than calling _log_message() avoids
    # creating a second, un-backdated in-progress run that would outrank `in_progress` below by
    # having a more recent started_at.
    MailboxMessage.objects.create(run=completed, uid=1, sender='hr@acme.test', subject='x', matched_job=applied_job)
    in_progress = MailboxRun.objects.create(fetched_count=1)
    MailboxRun.objects.filter(pk=in_progress.pk).update(started_at=timezone.now() - timezone.timedelta(seconds=30))

    r = client.get('/api/mailbox-runs/status/')

    assert r.data['estimate']['kind'] == 'incremental'
    assert r.data['estimate']['estimated_seconds'] == pytest.approx(5.0, abs=0.1)
    assert r.data['elapsed_seconds'] >= 30
    assert r.data['taking_longer_than_usual'] is True


def test_mailbox_run_status_requires_cv_owner(db, applied_job):
    other = User.objects.create_user('other12@example.test', email='other12@example.test', password='pw')
    other_client = APIClient(); other_client.force_authenticate(other)

    r = other_client.get('/api/mailbox-runs/status/')

    assert r.status_code == 404


# --- TASK-122 AC2/AC3/AC4/AC6/AC7: the draft-chat conversation -------------------------------------

def test_chat_turn_persists_history_and_rebuilds_it_on_the_next_turn(client, owner, applied_job, monkeypatch):
    """The genuine multi-turn proof: the second call's `history` argument must contain the first
    turn's (instruction, revision) pair -- "kuerzer" then "actually keep the date I just added" only
    makes sense if the first turn was remembered.
    """
    from jobradar.services.draft_chat import ChatTurnResult

    message = _log_message(applied_job, 'interview_invitation')
    draft = _written_draft(applied_job, message, body_text='Original draft text')
    captured = []

    def fake_run_chat_turn(original_draft_text, history, user_message, provider, model, effort, speed='normal', *, profile=None, timeout_seconds=None):
        captured.append({'original': original_draft_text, 'history': list(history), 'message': user_message})
        return ChatTurnResult(f'revision {len(captured)}', '')

    monkeypatch.setattr('jobradar.views.run_chat_turn', fake_run_chat_turn)

    r1 = client.post(f'/api/mailbox-drafts/{draft.id}/chat/', {'user_message': 'kuerzer', 'provider': 'anthropic', 'model': 'sonnet', 'effort': 'medium'}, format='json')
    assert r1.status_code == 200
    assert r1.data['chat_history'] == [{'user_message': 'kuerzer', 'revised_text': 'revision 1'}]
    assert captured[0]['history'] == []
    assert captured[0]['original'] == 'Original draft text'

    r2 = client.post(f'/api/mailbox-drafts/{draft.id}/chat/', {'user_message': 'actually keep the date I just added', 'provider': 'anthropic', 'model': 'sonnet', 'effort': 'medium'}, format='json')
    assert r2.status_code == 200
    assert len(captured) == 2
    assert captured[1]['history'][0].user_message == 'kuerzer'
    assert captured[1]['history'][0].revised_text == 'revision 1'
    assert captured[1]['original'] == 'Original draft text'  # the ORIGINAL, not the latest revision
    draft.refresh_from_db()
    assert [item['user_message'] for item in draft.chat_history] == ['kuerzer', 'actually keep the date I just added']

    owner.jobradar_profile.refresh_from_db()
    assert owner.jobradar_profile.mailbox_chat_provider == 'anthropic'
    assert owner.jobradar_profile.mailbox_chat_model == 'sonnet'


def test_chat_turn_for_a_job_the_user_cannot_see_is_404(client, applied_job):
    message = _log_message(applied_job, 'interview_invitation')
    draft = _written_draft(applied_job, message)
    other = User.objects.create_user('other13@example.test', email='other13@example.test', password='pw')
    other_client = APIClient(); other_client.force_authenticate(other)

    r = other_client.post(f'/api/mailbox-drafts/{draft.id}/chat/', {'user_message': 'kuerzer', 'provider': 'anthropic', 'model': 'sonnet', 'effort': 'medium'}, format='json')

    assert r.status_code == 404


def test_chat_turn_refuses_with_4xx_for_an_unavailable_model_without_invoking_a_real_model(client, applied_job):
    """AC7: an unavailable model is a refusal, not a 500 -- and validate_model_capability rejects a
    model name that is not in available_model_options() before anything is ever shelled out to, so
    this never launches a real model process."""
    message = _log_message(applied_job, 'interview_invitation')
    draft = _written_draft(applied_job, message, body_text='Original text')

    r = client.post(f'/api/mailbox-drafts/{draft.id}/chat/', {'user_message': 'kuerzer', 'provider': 'anthropic', 'model': 'no-such-model-xyz', 'effort': 'medium'}, format='json')

    assert r.status_code == 400
    assert 'detail' in r.data
    draft.refresh_from_db()
    assert draft.chat_history == []  # a refused turn is never persisted


def test_accepting_a_chat_revision_via_edit_writes_through_update_draft_text_and_resets_chat_history(client, applied_job, monkeypatch):
    """AC5: accepting is the existing `edit` action -- no second writer of Gmail/body_text. Also
    proves the conversation resets once its result is accepted, so a later chat turn starts fresh
    from the now-current text rather than re-feeding a transcript that ends at stale text.
    """
    message = _log_message(applied_job, 'interview_invitation')
    draft = _written_draft(applied_job, message, body_text='Original text')
    draft.chat_history = [{'user_message': 'kuerzer', 'revised_text': 'Shorter text'}]
    draft.save(update_fields=['chat_history'])
    calls = []
    _fake_gmail_transport(monkeypatch, calls)

    r = client.post(f'/api/mailbox-drafts/{draft.id}/edit/', {'body_text': 'Shorter text'}, format='json')

    assert r.status_code == 200
    draft.refresh_from_db()
    assert draft.body_text == 'Shorter text'
    assert draft.evaluator == 'human'
    assert calls == [('draft-1', 'thread-1')]  # went through update_draft_text's real Gmail write
    assert draft.chat_history == []


# --- TASK-122 AC3/AC4: the model picker, reused from CV generation's discovery ----------------------

def test_draft_chat_model_options_exposes_available_models_and_the_saved_choice(client, owner):
    from jobradar.services.prompt_builder import user_profile_settings as get_profile

    profile = get_profile(owner)
    profile.mailbox_chat_provider = 'anthropic'
    profile.mailbox_chat_model = 'sonnet'
    profile.save(update_fields=['mailbox_chat_provider', 'mailbox_chat_model'])

    r = client.get('/api/mailbox-drafts/model-options/')

    assert r.status_code == 200
    assert isinstance(r.data['models'], list)
    assert r.data['selected_provider'] == 'anthropic'
    assert r.data['selected_model'] == 'sonnet'
