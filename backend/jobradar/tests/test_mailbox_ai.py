import json
import subprocess
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from jobradar import views
from jobradar.models import JobLead, MailboxDraft, MailboxMessage, MailboxRun, MailboxSuggestion, UserProfile
from jobradar.services import mailbox, mailbox_ai


@pytest.fixture
def owner_client(db):
    user = get_user_model().objects.create_user('owner', password='pw', is_staff=True)
    UserProfile.objects.create(user=user)
    client = APIClient()
    client.force_authenticate(user)
    client.user = user
    return client


def message(**values):
    run = values.pop('run', None) or MailboxRun.objects.create()
    defaults = {'uid': MailboxMessage.objects.count() + 1, 'sender': 'recruiter@example.test', 'subject': 'Update', 'body_text': 'Application update', 'classification': 'uncertain', 'evaluator': 'heuristic'}
    defaults.update(values)
    return MailboxMessage.objects.create(run=run, **defaults)


def test_codex_batch_uses_strict_structured_output(monkeypatch):
    entries = [{'id': 7, 'sender': 'x', 'subject': 'Update', 'body': 'Thanks', 'sender_matches_tracked_job': False}]
    monkeypatch.setattr(mailbox_ai, 'codex_available', lambda: 'codex')

    def run(command, **kwargs):
        schema = json.loads(Path(command[command.index('--output-schema') + 1]).read_text())
        assert schema['properties']['results']['items']['additionalProperties'] is False
        Path(command[command.index('--output-last-message') + 1]).write_text(json.dumps({'results': [{'id': 7, 'classification': 'application_confirmed'}]}))
        return subprocess.CompletedProcess(command, 0, '', '')

    monkeypatch.setattr(mailbox_ai, '_run', run)

    assert mailbox_ai.classify_batch(entries, 'gpt-5.3-codex', 'low', 5) == {7: 'application_confirmed'}


def test_invalid_codex_batch_changes_nothing(db, monkeypatch):
    first = message(uid=1)
    second = message(uid=2)
    monkeypatch.setattr(mailbox_ai, 'classify_batch', lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError('bad output')))

    with pytest.raises(RuntimeError, match='bad output'):
        mailbox.review_uncertain_with_codex('model', 'low')

    first.refresh_from_db(); second.refresh_from_db()
    assert [(first.classification, first.evaluator), (second.classification, second.evaluator)] == [('uncertain', 'heuristic'), ('uncertain', 'heuristic')]


def test_successful_codex_review_only_updates_classification_and_evaluator(db, monkeypatch):
    job = JobLead.objects.create(company='ACME', title='Engineer', status='applied')
    promoted = message(uid=1, matched_job=job, body_text='Unfortunately we will not proceed')
    guarded = message(uid=2, sender='alerts@github.com', matched_job=job, body_text='Course sale: unfortunately no')
    before_jobs = list(JobLead.objects.values())
    monkeypatch.setattr(mailbox_ai, 'classify_batch', lambda entries, *args: {entry['id']: 'rejection' for entry in entries})

    result = mailbox.review_uncertain_with_codex('model', 'low')

    promoted.refresh_from_db(); guarded.refresh_from_db()
    assert (promoted.classification, promoted.evaluator) == ('rejection', 'codex')
    assert (guarded.classification, guarded.evaluator) == ('recruiter_reply', 'codex')
    assert result == {'reviewed': 2, 'changed': 2, 'remaining': 0}
    assert list(JobLead.objects.values()) == before_jobs
    assert MailboxSuggestion.objects.count() == MailboxDraft.objects.count() == 0


def test_local_ai_endpoint_reports_and_processes_a_bounded_batch(owner_client, settings, monkeypatch):
    settings.DEBUG = True
    for uid in range(12):
        message(uid=uid + 1)
    monkeypatch.setattr(views, 'available_model_options', lambda: [{'provider': 'openai', 'key': 'codex-model', 'label': 'Codex', 'efforts': ['low'], 'default_effort': 'low'}])
    monkeypatch.setattr(mailbox_ai, 'codex_available', lambda: 'codex')
    seen = {}

    def review(model, effort, limit=10):
        seen.update(model=model, effort=effort, limit=limit)
        return {'reviewed': 10, 'changed': 6, 'remaining': 2}

    monkeypatch.setattr(mailbox, 'review_uncertain_with_codex', review)

    status = owner_client.get('/api/mailbox-runs/local-ai-review/', REMOTE_ADDR='127.0.0.1')
    result = owner_client.post('/api/mailbox-runs/local-ai-review/', REMOTE_ADDR='127.0.0.1')

    assert status.data == {'local': True, 'supported': True, 'pending': 12, 'model': 'Codex', 'detail': ''}
    assert result.status_code == 200 and result.data['pending'] == 2
    assert seen == {'model': 'codex-model', 'effort': 'low', 'limit': 10}


def test_codex_review_is_unavailable_when_codex_is_missing(owner_client, settings, monkeypatch):
    settings.DEBUG = True
    monkeypatch.setattr(views, 'available_model_options', lambda: [{'provider': 'openai', 'key': 'model', 'label': 'Codex', 'efforts': ['low'], 'default_effort': 'low'}])
    monkeypatch.setattr(mailbox_ai, 'codex_available', lambda: None)

    status = owner_client.get('/api/mailbox-runs/local-ai-review/', REMOTE_ADDR='127.0.0.1')

    assert status.data['local'] is True and status.data['supported'] is False
    assert owner_client.post('/api/mailbox-runs/local-ai-review/', REMOTE_ADDR='127.0.0.1').status_code == 400


@pytest.mark.parametrize('debug,address', [(False, '127.0.0.1'), (True, '203.0.113.1')])
def test_codex_review_is_unavailable_off_the_local_loopback(owner_client, settings, monkeypatch, debug, address):
    settings.DEBUG = debug
    monkeypatch.setattr(mailbox_ai, 'codex_available', lambda: pytest.fail('must not probe Codex'))

    response = owner_client.get('/api/mailbox-runs/local-ai-review/', REMOTE_ADDR=address)
    assert response.data['local'] is False and response.data['supported'] is False
    assert owner_client.post('/api/mailbox-runs/local-ai-review/', REMOTE_ADDR=address).status_code == 404


def test_non_owner_cannot_reach_local_codex_review(db, settings):
    settings.DEBUG = True
    user = get_user_model().objects.create_user('other', password='pw')
    client = APIClient(); client.force_authenticate(user)

    assert client.get('/api/mailbox-runs/local-ai-review/', REMOTE_ADDR='127.0.0.1').status_code == 404
    assert client.post('/api/mailbox-runs/local-ai-review/', REMOTE_ADDR='127.0.0.1').status_code == 404


def test_cloud_workflow_is_hourly_forced_and_explicitly_non_llm():
    workflow = (Path(__file__).resolve().parents[3] / '.github/workflows/mailbox-check.yml').read_text()
    assert "cron: '17 * * * *'" in workflow
    assert 'workflow_dispatch:' in workflow
    assert 'LLM_PROVIDER: heuristic' in workflow
    assert 'check_mailbox --force' in workflow
    for secret in ('DATABASE_URL', 'GMAIL_OAUTH_CLIENT_ID', 'GMAIL_OAUTH_CLIENT_SECRET', 'GMAIL_OAUTH_REFRESH_TOKEN', 'CODEX_CV_OWNER_EMAIL'):
        assert '${{ secrets.%s }}' % secret in workflow
