"""TASK-258: a data import that moves an existing job to Applied runs TASK-256's metadata cleanup."""
from pathlib import Path

import pytest
from django.contrib.auth.models import User
from django.db import transaction

from jobradar.models import JobLead
from jobradar.services import user_data_portability
from jobradar.services.cv_generator import (
    _record_artifact_metadata, _sent_paths, _target_names, applicant_name, latest_generated_sources, persist_generated_files,
)
from jobradar.services.user_data_portability import import_user_export


@pytest.fixture
def owner(db):
    return User.objects.create_user('importer', password='pw')


@pytest.fixture
def workspace(settings, tmp_path):
    settings.CODEX_CV_WORKSPACE = str(tmp_path)
    return tmp_path


def _job(owner, status='new'):
    return JobLead.objects.create(company='ACME', title='Python Engineer', status=status, created_by=owner)


def _generate_files(workspace, job, user):
    # What generate_cv_package does after compiling: persist the documents, then record the sidecar.
    output = workspace/f'build-{job.id}'; output.mkdir()
    cv_name, letter_name = _target_names(job, applicant_name(user), 'Anschreiben')
    for name in (cv_name, letter_name):
        (output/name).write_text(f'{job.id} {name}', encoding='utf-8'); (output/name).with_suffix('.pdf').write_bytes(b'%PDF')
    saved = persist_generated_files(output, workspace, cv_name, letter_name)
    return saved, _record_artifact_metadata(job, user.id, saved, 'anschreiben')


def _payload(*jobs):
    return {'schema_version': 1, 'app': 'dachapply', 'duplicate_strategy': 'override',
            'data': {'jobs': list(jobs), 'evaluations': [], 'notes': [], 'followups': []}}


def test_import_moving_existing_job_to_applied_cleans_metadata_after_commit(owner, workspace, django_capture_on_commit_callbacks):
    job = _job(owner)
    sent, sidecar = _generate_files(workspace, job, owner)
    with django_capture_on_commit_callbacks() as callbacks:
        result = import_user_export(owner, _payload({'id': job.id, 'status': 'applied'}))
        # Nothing is cleaned while the import's transaction is still open.
        assert sidecar.exists()
    assert not result['errors'] and result['updated'] == {'jobs': 1}
    assert len(callbacks) == 1
    callbacks[0]()
    assert not sidecar.exists()
    # Same outcome as the board PATCH: the documents stay, read-only, linked to the Applied job.
    assert all(Path(path).exists() for path in sent.values())
    assert latest_generated_sources(job, owner, 'anschreiben') == (sent['cv_tex'], sent['letter_tex'])
    assert {str(Path(p).resolve()) for p in sent.values()} <= {str(Path(p).resolve()) for p in _sent_paths(workspace)}


def test_rolled_back_import_leaves_metadata_untouched(owner, workspace, django_capture_on_commit_callbacks):
    job = _job(owner)
    _, sidecar = _generate_files(workspace, job, owner)
    with django_capture_on_commit_callbacks(execute=True) as callbacks, pytest.raises(RuntimeError):
        with transaction.atomic():
            import_user_export(owner, _payload({'id': job.id, 'status': 'applied'}))
            raise RuntimeError('rolled back')
    job.refresh_from_db()
    assert job.status == 'new' and sidecar.exists() and callbacks == []
    # Control: the same import committed does register the cleanup, so the empty list above is the
    # rollback discarding it rather than the hook never existing.
    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        import_user_export(owner, _payload({'id': job.id, 'status': 'applied'}))
    assert len(callbacks) == 1 and not sidecar.exists()


@pytest.mark.parametrize('before,incoming', [
    ('applied', {'status': 'applied', 'title': 'Renamed'}),  # already Applied: no transition
    ('new', {'status': 'interview'}),                          # a non-applied status
    ('new', {'title': 'Renamed'}),                              # status not touched
])
def test_import_without_applied_transition_keeps_metadata(owner, workspace, django_capture_on_commit_callbacks, monkeypatch, before, incoming):
    calls = []
    monkeypatch.setattr(user_data_portability, 'delete_generated_metadata', calls.append)
    job = _job(owner, status=before)
    _, sidecar = _generate_files(workspace, job, owner)
    with django_capture_on_commit_callbacks(execute=True):
        result = import_user_export(owner, _payload({'id': job.id, **incoming}))
    assert result['updated'] == {'jobs': 1} and calls == [] and sidecar.exists()


def test_import_creating_an_applied_job_runs_no_cleanup(owner, workspace, django_capture_on_commit_callbacks, monkeypatch):
    calls = []
    monkeypatch.setattr(user_data_portability, 'delete_generated_metadata', calls.append)
    with django_capture_on_commit_callbacks(execute=True):
        result = import_user_export(owner, _payload({'id': 99999, 'company': 'New Co', 'title': 'Role', 'status': 'applied'}))
    assert result['created'] == {'jobs': 1} and calls == []


def test_cleanup_error_never_fails_the_import(owner, workspace, django_capture_on_commit_callbacks, monkeypatch):
    calls = []
    def broken(job):
        calls.append(job.id)
        raise OSError('workspace unavailable')
    monkeypatch.setattr(user_data_portability, 'delete_generated_metadata', broken)
    job = _job(owner)
    with django_capture_on_commit_callbacks(execute=True):
        result = import_user_export(owner, _payload({'id': job.id, 'status': 'applied', 'title': 'Renamed'}))
    assert calls == [job.id]  # the cleanup really ran and really raised
    assert not result['errors'] and result['updated'] == {'jobs': 1}
    job.refresh_from_db()
    assert job.status == 'applied' and job.title == 'Renamed'
