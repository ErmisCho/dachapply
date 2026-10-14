"""TASK-288: the feedback-deadline popup's follow-up draft. Same seams as test_draft_chat.py --
available_model_options, `_binary_for` and `_run` are stubbed, so no test spawns a real CLI or model.
"""
import json
import subprocess
from datetime import date, datetime, timezone as dt_timezone

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from jobradar.models import JobEvaluation, JobLead, MailboxMessage, MailboxRun
from jobradar.services import cv_generator, draft_chat
from jobradar.services.prompt_builder import user_profile_settings

CLAUDE_MODEL = {
    'provider': 'anthropic', 'key': 'sonnet', 'label': 'Claude Sonnet',
    'efforts': ['low', 'medium', 'high'], 'default_effort': 'medium', 'fast_tier': '',
}
POSTING = 'We need a Django engineer who has shipped Postgres-backed APIs.'


@pytest.fixture(autouse=True)
def _env(settings, monkeypatch):
    settings.CODEX_CV_ENABLED = True
    settings.CODEX_CV_OWNER_EMAIL = 'owner@example.test'
    settings.GMAIL_IMAP_USER = 'owner@example.test'
    settings.MAILBOX_SALARY_FLOOR_EUR = ''
    settings.MAILBOX_DO_NOT_DISCLOSE = []
    for module in (cv_generator, draft_chat):
        monkeypatch.setattr(module, 'available_model_options', lambda: [CLAUDE_MODEL])


@pytest.fixture
def owner(db):
    user = User.objects.create_user('owner@example.test', email='owner@example.test', password='pw')
    profile = user_profile_settings(user)
    profile.candidate_profile = 'Backend developer, 6 years of Python.'
    profile.save()
    return user


@pytest.fixture
def job(owner):
    job = JobLead.objects.create(company='Acme', title='Engineer', raw_description=POSTING, status='applied', applied_at=date(2026, 9, 1), feedback_due_date=date(2026, 10, 10), created_by=owner)
    JobEvaluation.objects.create(job=job, fit_score=82, priority='high', recommendation='apply', matched_skills=['Django'], missing_skills=['Kafka'])
    run = MailboxRun.objects.create()
    MailboxMessage.objects.create(run=run, uid=1, sender='me@example.test', to_addrs='hr@acme.test', subject='Application: Engineer', body_text='Please find my application attached.', matched_job=job, sent_by_owner=True, received_at=datetime(2026, 9, 1, tzinfo=dt_timezone.utc))
    MailboxMessage.objects.create(run=run, uid=2, sender='Jane HR <hr@acme.test>', subject='Re: Application: Engineer', body_text='Thanks, we will get back to you within two weeks.', matched_job=job, received_at=datetime(2026, 9, 3, tzinfo=dt_timezone.utc))
    return job


def _post(owner, job):
    client = APIClient()
    client.force_authenticate(owner)
    return client.post(f'/api/jobs/{job.id}/followup-draft/', {}, format='json')


def test_prompt_carries_posting_evaluation_profile_dates_and_the_whole_conversation_in_order(job):
    messages = list(job.mailbox_messages.order_by('received_at'))
    prompt = draft_chat.build_followup_prompt(job, job.evaluations.first(), messages, 'Backend developer, 6 years of Python.')
    assert POSTING in prompt
    assert 'Please find my application attached.' in prompt and 'CANDIDATE (me)' in prompt
    assert 'we will get back to you within two weeks' in prompt and 'THEY (Jane HR <hr@acme.test>)' in prompt
    assert prompt.index('Please find my application') < prompt.index('get back to you within two weeks')
    assert 'Fit score: 82/100' in prompt and 'Missing skills: Kafka' in prompt
    assert '6 years of Python' in prompt and '2026-09-01' in prompt and '2026-10-10' in prompt


def test_endpoint_returns_a_threaded_draft_built_from_that_prompt(owner, job, monkeypatch):
    seen = {}

    def fake_run(command, **kwargs):
        seen['prompt'] = kwargs['input']
        return subprocess.CompletedProcess(command, 0, stdout=json.dumps({'structured_output': {'revised_text': 'Dear Jane, ...'}}), stderr='')
    monkeypatch.setattr(draft_chat, '_binary_for', lambda provider: 'claude')
    monkeypatch.setattr(draft_chat, '_run', fake_run)

    body = _post(owner, job).json()

    assert body['reason'] == '' and body['body_text'] == 'Dear Jane, ...'
    assert body['to'] == ['hr@acme.test'] and body['subject'] == 'Re: Application: Engineer'
    assert body['reply_to_message_id'] == MailboxMessage.objects.get(uid=2).pk
    assert POSTING in seen['prompt'] and 'get back to you within two weeks' in seen['prompt']


def test_without_any_model_the_popup_still_gets_recipient_subject_and_a_reason(owner, job, monkeypatch):
    for module in (cv_generator, draft_chat):
        monkeypatch.setattr(module, 'available_model_options', lambda: [])
    response = _post(owner, job)
    assert response.status_code == 200
    assert response.json()['body_text'] == '' and 'no drafting model is available' in response.json()['reason']
    assert response.json()['to'] == ['hr@acme.test']


def test_a_missing_cli_is_reported_as_the_reason(owner, job, monkeypatch):
    monkeypatch.setattr(draft_chat, '_binary_for', lambda provider: None)
    monkeypatch.setattr(draft_chat, '_run', lambda *a, **k: pytest.fail('no process may be spawned'))
    assert 'CLI is not installed' in _post(owner, job).json()['reason']
