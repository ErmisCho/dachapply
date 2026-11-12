"""TASK-372.1: local intake only; all files live in pytest's system temporary directory."""
import hashlib
import importlib
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest

from jobradar.services import error_occurrences as errors


@pytest.fixture
def store(settings, tmp_path):
    settings.DEBUG = True
    settings.ERROR_OCCURRENCE_LOCAL_DB = str(tmp_path / 'occurrences.sqlite3')
    return tmp_path / 'occurrences.sqlite3'


@pytest.mark.parametrize('source', errors.SOURCES)
def test_source_intake_redaction_and_non_errors(store, source):
    secret = 'Bearer secret cookie session postgres://user:password@host CV candidate prompt mail /private/file'
    ids = errors.ingest(source, [{'id': secret, 'operation': secret, 'status': 'failed',
                                 'summary': secret, 'error_type': secret, 'evidence': secret},
                                {'id': 'ok', 'status': 'success'}, {'id': 'warn', 'status': 'warning'}])
    rows = errors.unresolved()
    assert len(ids) == len(rows) == 1
    assert rows[0]['id'] == ids[0] and rows[0]['at']
    assert rows[0]['source'] == source and rows[0]['environment'] == 'local'
    assert rows[0]['evidence'] == 'occurrence:' + ids[0]
    assert secret not in json.dumps(rows)
    assert b'Bearer secret' not in store.read_bytes()


def test_replay_restart_rotation_and_atomic_progress(store):
    event = {'id': 'generation1:42', 'status': 'failed'}
    first = errors.ingest('backend', [event], cursor='generation1:43')
    importlib.reload(errors)
    assert errors.progress('backend') == hashlib.sha256(b'generation1:43').hexdigest()
    assert errors.ingest('backend', [event]) == first
    second = errors.ingest('backend', [{'id': 'generation2:42', 'status': 'failed'}], cursor='generation2:43')
    assert first != second and len(errors.unresolved()) == 2
    # Failed batches cannot move progress or leave partial evidence.
    assert errors.ingest('backend', [{'id': 'new', 'status': 'failed'}, {'status': 'failed'}], cursor='bad') == []
    assert len(errors.unresolved()) == 2
    assert errors.progress('backend') == hashlib.sha256(b'generation2:43').hexdigest()


def test_concurrent_replay_and_distinct_failures(store):
    def write(index):
        return errors.capture('backend', f'run:{index % 8}')
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(write, range(32)))
    assert all(results)
    assert len(errors.unresolved()) == 8


def test_bounded_storage_and_failure_without_logging(store, monkeypatch, caplog):
    monkeypatch.setattr(errors, 'MAX_ROWS', 1)
    assert errors.capture('backend', 'one')
    assert not errors.capture('backend', 'two')
    assert errors.health() == 'degraded'
    assert len(errors.unresolved()) == 1
    assert not caplog.records
    monkeypatch.setattr(errors, '_connect', lambda: (_ for _ in ()).throw(OSError('private secret')))
    assert not errors.capture('backend')
    assert errors.health() == 'degraded'
    assert not caplog.records


def test_oversized_batch_rolls_back(store):
    assert not errors.ingest('backend', ({'id': i, 'status': 'failed'} for i in range(101)), cursor='bad')
    assert errors.unresolved() == [] and errors.progress('backend') is None
    assert errors.capture('backend', 'recovery')
    assert errors.health() == 'ok'


def test_disabled_and_production_unavailable(store, settings):
    settings.DEBUG = False
    assert not errors.capture('backend') and errors.health() == 'degraded'
    assert not store.exists()
    settings.ERROR_OCCURRENCE_LOCAL_DB = ''
    assert not errors.capture('backend') and errors.health() == 'disabled'


def test_logging_filters_warning_and_never_formats_payload(store):
    handler = errors.OccurrenceHandler()
    for level in (logging.INFO, logging.WARNING, logging.ERROR):
        handler.emit(logging.LogRecord('jobradar', level, '/secret', 1, '%s %s', ('secret',), None))
    assert len(errors.unresolved()) == 1


def test_caught_worker_and_provider_failures(store, monkeypatch):
    from jobradar.services import application_prep, cv_generator, cv_tasks, mailbox_tasks
    data = {}
    monkeypatch.setattr(application_prep, '_edit_sidecar', lambda job, user_id, edit: edit(data))
    application_prep._save(SimpleNamespace(pk=1), 1, lambda prep: prep.update(reason='Analysis failed secret'))
    cv_tasks._update('fake-document', status='failed', error='private CV')
    cv_tasks._update('fake-document', status='failed', error='private CV')
    mailbox_tasks._update('fake-mailbox', status='failed', error='private mail')
    cv_generator._provider_failure('private prompt')
    assert sorted(row['source'] for row in errors.unresolved()) == ['document', 'mailbox', 'pipeline', 'provider']


def test_compile_failed_attempt_even_before_repair(store, tmp_path, monkeypatch):
    from jobradar.services import cv_generator
    monkeypatch.setattr(cv_generator.shutil, 'which', lambda name: 'pdflatex')
    monkeypatch.setattr(cv_generator, '_run_command', lambda *a, **kw: SimpleNamespace(returncode=1, stdout='private TeX', stderr=''))
    monkeypatch.setattr(cv_generator, '_save_failed_compile', lambda *a: {})
    with pytest.raises(cv_generator.RecoverableGenerationError):
        cv_generator._compile_pdf(tmp_path, 'cv.tex', True)
    assert [row['source'] for row in errors.unresolved()] == ['compile']


def test_real_500_capture(store, settings, db):
    from django.test import Client
    settings.ROOT_URLCONF = 'jobradar.tests.test_error_alerting'
    assert Client(raise_request_exception=False).get('/boom/').status_code == 500
    assert [row['source'] for row in errors.unresolved()] == ['backend']


def test_mailbox_returned_failure(store, settings, db, monkeypatch):
    from django.contrib.auth.models import User
    from jobradar.services import mailbox
    from jobradar.services.prompt_builder import user_profile_settings
    settings.GMAIL_IMAP_USER = 'owner@example.test'
    settings.GMAIL_IMAP_APP_PASSWORD = 'fake'
    settings.CODEX_CV_OWNER_EMAIL = 'owner@example.test'
    user = User.objects.create_user('owner@example.test', email='owner@example.test')
    profile = user_profile_settings(user)
    profile.mailbox_check_calendar_aware = False
    profile.save(update_fields=['mailbox_check_calendar_aware'])
    monkeypatch.setattr(mailbox, 'is_within_check_window', lambda *a: True)
    monkeypatch.setattr('jobradar.services.followup_digest.reconcile_sent_followups', lambda *a: None)
    class BrokenTransport:
        def fetch_new(self, last_uid):
            raise RuntimeError('private mail and token')
    first = mailbox.run_check(force=True, transport=BrokenTransport())
    second = mailbox.run_check(force=True, transport=BrokenTransport())
    assert first.error and second.error and first.pk != second.pk
    assert len(errors.unresolved()) == 2
    assert {row['source'] for row in errors.unresolved()} == {'mailbox'}


def test_coverage_matrix_is_explicit():
    text = (Path(__file__).resolve().parents[3] / 'docs/error-occurrences.md').read_text(encoding='utf-8')
    for source in ('Backend exceptions / HTTP 500', 'Pipeline', 'Document', 'Provider', 'TeX compile', 'Mailbox'):
        assert any(source in row and 'Connected:' in row for row in text.splitlines())
    for source in ('Browser exceptions', 'Failing CI / deploy runs', 'Historical benchmark', 'Azure production'):
        assert any(source in row and 'Unavailable:' in row and ('Requires' in row or 'Needs' in row or 'needs' in row) for row in text.splitlines())
