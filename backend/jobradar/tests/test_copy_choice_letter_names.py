"""TASK-279: Copy TeX per document, and legacy '<applicant>-Letter-<target>' letters take their label.

Hermetic: every file lives under tmp_path, no worker thread runs (Thread is replaced by a recorder),
no model, LaTeX or clipboard is touched.
"""
import time
from pathlib import Path


import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from jobradar.models import JobLead
from jobradar.services import cv_generator, cv_tasks
from jobradar.services.cv_generator import _record_artifact_metadata, _target_slug, applicant_name, latest_generated_sources, rename_generated_artifact

URL = 'https://jobs.example.com/techsearch'


@pytest.fixture
def workspace(settings, tmp_path):
    settings.CODEX_CV_WORKSPACE = str(tmp_path)
    settings.CODEX_CV_ENABLED = True
    settings.CODEX_CV_CACHE = False
    settings.CODEX_CV_OWNER_EMAIL = 'owner@example.test'
    return tmp_path


@pytest.fixture
def owner(db, cv_assets):
    user = User.objects.create_user('owner', email='owner@example.test', password='pw')
    cv_assets(user)
    return user


@pytest.fixture
def client(owner):
    api = APIClient(); api.force_authenticate(owner)
    return api


@pytest.fixture
def job(owner):
    return JobLead.objects.create(company='Techsearch', title='AI Developerin', url=URL, created_by=owner, raw_description='AI',
                                  original_source_text='AI developer role with enough original posting text to generate from.')


@pytest.fixture
def started(monkeypatch):
    """Records each worker a task would start instead of running it."""
    calls = []
    class Recorder:
        def __init__(self, target, args, **kwargs): self.args = args
        def start(self): calls.append(self.args)
    monkeypatch.setattr(cv_tasks, 'Thread', Recorder)
    return calls


def _legacy_letter(workspace, job, user, tracked=True, key='motivationsschreiben'):
    output = workspace/'output'; output.mkdir(exist_ok=True)
    tex = output/f'{applicant_name(user)}-Letter-{_target_slug(job)}.tex'
    tex.write_text('LETTER BODY', encoding='utf-8'); tex.with_suffix('.pdf').write_bytes(b'%PDF letter')
    if tracked:  # a revision made after TASK-253 recorded the old-named file under its template key
        _record_artifact_metadata(job, user.id, {'letter_tex': str(tex), 'letter_pdf': str(tex.with_suffix('.pdf'))}, key)
    return tex


def _labelled(job, user):
    return f'{applicant_name(user)}-Motivationsschreiben-{_target_slug(job)}'


def _revise(job, user, letter):
    return cv_tasks.start_cv_task(job.id, user.id, 'profile', 'de', 'motivationsschreiben', True, 'openai', 'gpt', 'low', 'normal',
                                  source_letter=str(letter), revision_instructions='shorter', create_cv=False)


# --- copy choice --------------------------------------------------------------------------------

def test_parts_hold_each_document_with_the_job_link_line(tmp_path):
    cv = tmp_path/'cv.tex'; cv.write_text('CV BODY', encoding='utf-8')
    letter = tmp_path/'letter.tex'; letter.write_text('LETTER BODY', encoding='utf-8')
    both = {'cv_tex': str(cv), 'letter_tex': str(letter), 'cv_pdf': 'x.pdf'}
    assert cv_tasks._clipboard_parts(both, URL) == {'cv': f'% Job listing: {URL}\n\nCV BODY', 'letter': f'% Job listing: {URL}\n\nLETTER BODY'}
    assert cv_tasks._clipboard_parts({'cv_tex': str(cv), 'letter_tex': str(tmp_path/'gone.tex')}, URL) == {'cv': f'% Job listing: {URL}\n\nCV BODY'}
    assert cv_tasks._clipboard_parts({}, URL) == {}


def test_finished_tasks_and_the_preview_return_parts_beside_the_unchanged_combined_copy(client, owner, job, workspace, monkeypatch, started):
    cv = workspace/'cv.tex'; cv.write_text('CV BODY', encoding='utf-8')
    letter = workspace/'letter.tex'; letter.write_text('LETTER BODY', encoding='utf-8')
    artifacts = {'cv_tex': str(cv), 'letter_tex': str(letter)}
    copied = []
    monkeypatch.setattr(cv_tasks, '_copy_to_clipboard', lambda text: copied.append(text) or True)
    monkeypatch.setattr(cv_tasks, 'recompile_generated_package', lambda *a, **k: (b'zip', 'a.zip', dict(artifacts)))
    task_id = cv_tasks.start_cv_compile_task(job.id, owner.id, 'de', str(cv), str(letter))
    assert cv_tasks.get_cv_task(task_id, owner.id)['clipboard_tex_parts'] == {}  # same shape while queued
    cv_tasks._run_compile(*started[-1])  # the recorded worker, run in this thread
    task = cv_tasks.get_cv_task(task_id, owner.id)
    combined = cv_tasks._clipboard_payload(artifacts, URL)
    # AC3: the automatic copy still takes every document.
    assert task['clipboard_tex'] == combined and copied == [combined] and task['clipboard_copied'] is True
    assert task['clipboard_tex_parts'] == {'cv': f'% Job listing: {URL}\n\nCV BODY', 'letter': f'% Job listing: {URL}\n\nLETTER BODY'}
    noop = cv_tasks.start_cv_noop_task(job.id, owner.id, {'letter_tex': str(letter)})
    assert cv_tasks.get_cv_task(noop, owner.id)['clipboard_tex_parts'] == {'letter': f'% Job listing: {URL}\n\nLETTER BODY'}
    tex = _legacy_letter(workspace, job, owner, key='anschreiben')
    # The preview shows the detected language's first letter: German, so the Anschreiben.
    job.language_requirements = 'Deutsch und Englisch, Erfahrung mit der Entwicklung'; job.save(update_fields=['language_requirements'])
    preview =client.get(f'/api/jobs/{job.id}/cv-generation/').data
    assert preview['clipboard_tex_parts'] == {'letter': cv_tasks._clipboard_payload({'letter_tex': str(tex)}, URL)}


# --- legacy letter names ------------------------------------------------------------------------

@pytest.mark.parametrize('tracked', [True, False])
def test_a_revision_renames_a_legacy_letter_to_its_label_and_the_next_revision_finds_it(owner, job, workspace, started, tracked):
    old = _legacy_letter(workspace, job, owner, tracked)
    cv_tasks._tasks['old'] = {'id': 'old', 'user_id': owner.id, 'job_id': job.id, 'status': 'ready', 'artifacts': {'letter_tex': str(old)}, 'updated_at': time.time()}
    try:
        _revise(job, owner, old)
        new = old.with_name(_labelled(job, owner)+'.tex')
        assert new.read_text(encoding='utf-8') == 'LETTER BODY' and new.with_suffix('.pdf').read_bytes() == b'%PDF letter'
        assert not old.exists() and not old.with_suffix('.pdf').exists()
        assert started[-1][12] == str(new)  # the revision works on the renamed file
        assert cv_tasks._tasks['old']['artifacts']['letter_tex'] == str(new)  # finished tasks follow
        assert latest_generated_sources(job, owner, 'motivationsschreiben')[1] == str(new)
        # Not recorded as an owner-chosen name, and the next revision leaves it alone.
        assert cv_generator.preferred_names(job, owner, 'motivationsschreiben') == (None, None)
        _revise(job, owner, new)
        assert started[-1][12] == str(new) and new.exists()
    finally:
        cv_tasks._tasks.pop('old', None)


def test_recompile_renames_through_the_same_guard(client, owner, job, workspace, started):
    old = _legacy_letter(workspace, job, owner)
    response = client.post(f'/api/jobs/{job.id}/cv-generation/recompile-latest/', {'cv_template': 'de', 'letter_template': 'motivationsschreiben', 'create_cv': False}, format='json')
    assert response.status_code == 202, response.data
    new = old.with_name(_labelled(job, owner)+'.tex')
    assert new.exists() and not old.exists() and started[-1][5] == str(new)


def test_exact_edit_keeps_its_edit_after_the_rename(owner, job, workspace, started):
    old = _legacy_letter(workspace, job, owner)
    report = {'changed_files': [old.name], 'main_changes': [], 'unsupported_requirements_not_claimed': []}
    cv_tasks.start_cv_compile_task(job.id, owner.id, 'de', None, str(old), source_updates={str(old): 'EDITED'}, task_report=report, letter_key='motivationsschreiben')
    new = old.with_name(_labelled(job, owner)+'.tex')
    assert started[-1][5] == str(new) and started[-1][6] == {str(new): 'EDITED'}
    assert started[-1][7]['changed_files'] == [new.name]  # the report names the file as it now is


def test_a_taken_label_name_overwrites_nothing_and_keeps_the_old_name(owner, job, workspace, started):
    old = _legacy_letter(workspace, job, owner)
    taken = old.with_name(_labelled(job, owner)+'.pdf'); taken.write_bytes(b'someone else')
    _revise(job, owner, old)
    assert taken.read_bytes() == b'someone else' and not taken.with_suffix('.tex').exists()
    assert old.exists() and old.with_suffix('.pdf').exists() and started[-1][12] == str(old)


def test_a_letter_the_owner_named_is_not_renamed(owner, job, workspace, started):
    old = _legacy_letter(workspace, job, owner)
    mine = f'{applicant_name(owner)}-Letter-My-Own-Name'
    rename_generated_artifact(job, owner, 'letter', 'motivationsschreiben', mine)
    chosen = old.with_name(mine+'.tex')
    _revise(job, owner, chosen)
    assert chosen.exists() and started[-1][12] == str(chosen)


def test_a_sent_letter_is_not_renamed(owner, job, workspace, started):
    old = _legacy_letter(workspace, job, owner)
    cv_generator.delete_generated_metadata(job)  # Applied: the letter is now a read-only sent document
    assert latest_generated_sources(job, owner, 'motivationsschreiben')[1] == str(old)
    _revise(job, owner, old)
    assert old.exists() and started[-1][12] == str(old)


def test_a_template_labelled_letter_keeps_its_name(owner, job, workspace, started):
    old = _legacy_letter(workspace, job, owner)
    cv_tasks.start_cv_task(job.id, owner.id, 'profile', 'de', '', True, 'openai', 'gpt', 'low', 'normal',
                           source_letter=str(old), revision_instructions='shorter', create_cv=False)
    assert old.exists() and started[-1][12] == str(old)


def test_the_fresh_copy_of_a_sent_legacy_letter_takes_its_label(owner, job, workspace, monkeypatch):
    old = _legacy_letter(workspace, job, owner)
    cv_generator.delete_generated_metadata(job)  # Applied: the 'Letter' file is now a read-only sent document
    monkeypatch.setattr(cv_generator, '_compile_pdf', lambda output, filename, *a, **k: (output/Path(filename).with_suffix('.pdf')).write_bytes(b'%PDF new'))
    _, _, saved = cv_generator.recompile_generated_package(job, 'de', source_letter=str(old), user_id=owner.id, source_updates={str(old): 'EDITED'})
    new = old.with_name(_labelled(job, owner)+'.tex')
    assert saved['letter_tex'] == str(new) and new.read_text(encoding='utf-8') == 'EDITED'
    assert old.read_text(encoding='utf-8') == 'LETTER BODY'  # the sent file is untouched
    assert latest_generated_sources(job, owner, 'motivationsschreiben')[1] == str(new)
