"""TASK-265: a finished generation moves an unapplied job to 'ready_to_submit'; TASK-261: bulk runs
can skip the server-side clipboard copy.

Hermetic like test_clipboard_url.py: generate_cv_package / recompile_generated_package /
_copy_to_clipboard are replaced, and the workers run in-thread so their writes share this test's
transaction.
"""
from io import StringIO
from threading import Event

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command

from jobradar.management.commands import mark_ready_to_submit as command
from jobradar.models import JobLead
from jobradar.services import cv_tasks


@pytest.fixture
def owner(db):
    return User.objects.create_user('ready-owner', password='pw')


@pytest.fixture
def files(tmp_path):
    cv = tmp_path / 'cv.tex'; cv.write_text('CV', encoding='utf-8')
    letter = tmp_path / 'letter.tex'; letter.write_text('LETTER', encoding='utf-8')
    return {'cv_tex': str(cv), 'letter_tex': str(letter)}


def _job(owner, status='new'):
    return JobLead.objects.create(company='ACME', title='Engineer', status=status, created_by=owner)


def _run(job, monkeypatch, artifacts, fail=False, create_cv=True, create_letter=True, **kwargs):
    updates = []
    copied = []
    monkeypatch.setattr(cv_tasks, '_update', lambda task_id, **values: updates.append(values))
    monkeypatch.setattr(cv_tasks, '_copy_to_clipboard', lambda text: copied.append(text) or True)
    def generate(*a, **k):
        if fail:
            raise RuntimeError('provider down')
        return b'zip', 'a.zip', dict(artifacts)
    monkeypatch.setattr(cv_tasks, 'generate_cv_package', generate)
    cv_tasks._run('t', job.id, job.created_by_id, 'p', 'en', 'motivation_letter' if create_letter else '', create_letter,
                  'openai', 'gpt-5.5', 'medium', 'normal', create_cv=create_cv, cancel_event=Event(), **kwargs)
    return updates[-1], copied


@pytest.mark.parametrize('kind', ['cv', 'letter', 'both'])
@pytest.mark.parametrize('start', ['new', 'reviewed', 'to_apply'])
def test_successful_generation_moves_unapplied_job_to_ready_to_submit(owner, files, monkeypatch, kind, start):
    artifacts = {'both': files, 'cv': {'cv_tex': files['cv_tex']}, 'letter': {'letter_tex': files['letter_tex']}}[kind]
    job = _job(owner, start)
    final, _ = _run(job, monkeypatch, artifacts, create_cv=kind != 'letter', create_letter=kind != 'cv')
    assert final['status'] == 'ready'
    job.refresh_from_db()
    assert job.status == 'ready_to_submit'
    assert job.status_date is None


@pytest.mark.parametrize('status', ['applied', 'interview', 'offer', 'accepted', 'rejected', 'withdrawn', 'skipped', 'archived'])
def test_generation_never_changes_applied_or_later_status(owner, files, monkeypatch, status):
    job = _job(owner, status)
    _run(job, monkeypatch, files)
    job.refresh_from_db()
    assert job.status == status


def test_failed_generation_leaves_status_alone(owner, files, monkeypatch):
    job = _job(owner, 'to_apply')
    final, _ = _run(job, monkeypatch, files, fail=True)
    assert final['status'] == 'failed'
    job.refresh_from_db()
    assert job.status == 'to_apply'


def test_recompile_also_marks_ready(owner, files, monkeypatch):
    job = _job(owner, 'reviewed')
    monkeypatch.setattr(cv_tasks, '_update', lambda task_id, **values: None)
    monkeypatch.setattr(cv_tasks, '_copy_to_clipboard', lambda text: True)
    monkeypatch.setattr(cv_tasks, 'recompile_generated_package', lambda *a, **k: (b'zip', 'a.zip', dict(files)))
    cv_tasks._run_compile('t', job.id, owner.id, 'en', files['cv_tex'], files['letter_tex'], {}, None, Event())
    job.refresh_from_db()
    assert job.status == 'ready_to_submit'


def test_auto_clipboard_false_skips_copy_but_keeps_tex(owner, files, monkeypatch):
    job = _job(owner)
    final, copied = _run(job, monkeypatch, files, auto_clipboard=False)
    assert copied == []
    assert final['clipboard_copied'] is False
    assert 'CV' in final['clipboard_tex'] and 'LETTER' in final['clipboard_tex']
    final, copied = _run(job, monkeypatch, files)
    assert len(copied) == 1 and final['clipboard_copied'] is True


def test_copy_text_to_clipboard_wraps_private_helper(monkeypatch):
    monkeypatch.setattr(cv_tasks, '_copy_to_clipboard', lambda text: text == 'x')
    assert cv_tasks.copy_text_to_clipboard('x') is True


def test_command_dry_run_writes_nothing_and_apply_writes(owner, files, monkeypatch):
    with_files = _job(owner, 'to_apply')
    without_files = _job(owner, 'new')
    applied = _job(owner, 'applied')
    monkeypatch.setattr(command, 'latest_generated_sources',
                        lambda job, user, letter_key='': (files['cv_tex'], None) if job.id in (with_files.id, applied.id) else (None, None))
    out = StringIO()
    call_command('mark_ready_to_submit', stdout=out)
    assert f'job {with_files.id} ' in out.getvalue() and f'job {applied.id} ' not in out.getvalue()
    assert 'Dry run: 1 job(s)' in out.getvalue()
    assert set(JobLead.objects.values_list('status', flat=True)) == {'to_apply', 'new', 'applied'}
    out = StringIO()
    call_command('mark_ready_to_submit', '--apply', stdout=out)
    assert 'Moved 1 of 1' in out.getvalue()
    for job, expected in ((with_files, 'ready_to_submit'), (without_files, 'new'), (applied, 'applied')):
        job.refresh_from_db()
        assert job.status == expected
