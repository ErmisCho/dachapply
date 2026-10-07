"""TASK-271: rename generated files in the app or in Explorer, and keep tracking them."""
import os
import json
import zipfile
from io import BytesIO
from pathlib import Path

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from jobradar.models import JobLead
from jobradar.services import cv_generator, cv_tasks
from jobradar.services.cv_generator import (
    _record_artifact_metadata, _sent_paths, _target_names, applicant_name, latest_generated_artifacts,
    latest_generated_sources, persist_generated_files,
)


@pytest.fixture
def workspace(settings, tmp_path):
    settings.CODEX_CV_WORKSPACE = str(tmp_path)
    settings.CODEX_CV_ENABLED = True
    settings.CODEX_CV_CACHE = False
    settings.CODEX_CV_OWNER_EMAIL = 'owner@example.test'
    return tmp_path


@pytest.fixture
def owner(db):
    return User.objects.create_user('owner', email='owner@example.test', password='pw')


@pytest.fixture
def client(owner):
    api = APIClient(); api.force_authenticate(owner)
    return api


def _job(owner, company='ACME', title='Python Engineer'):
    return JobLead.objects.create(company=company, title=title, raw_description='Python Django SQL', created_by=owner,
                                  original_source_text='Python Django SQL role with enough original posting text to generate from.')


def _generate(workspace, job, user, content=None):
    # What generate_cv_package does after compiling: persist the documents, then record the sidecar.
    output = workspace/f'build-{job.id}-{len(list(workspace.glob("build-*")))}'; output.mkdir()
    cv_name, letter_name = _target_names(job, applicant_name(user), 'Anschreiben')
    for name in (cv_name, letter_name):
        (output/name).write_text(content or f'{job.id} {name}', encoding='utf-8')
        (output/name).with_suffix('.pdf').write_bytes(f'%PDF {job.id} {name}'.encode())
    saved = persist_generated_files(output, workspace, cv_name, letter_name)
    _record_artifact_metadata(job, user.id, saved, 'anschreiben')
    return saved


def _rename(client, job, name, artifact='cv'):
    return client.post(f'/api/jobs/{job.id}/cv-generation/rename/', {'artifact': artifact, 'letter_template': 'anschreiben', 'name': name}, format='json')


# --- AC1/AC2: in-app rename ---------------------------------------------------------------------

def test_rename_moves_tex_and_pdf_together_and_the_preview_shows_the_new_paths(client, owner, workspace, cv_assets):
    cv_assets(owner); job = _job(owner); saved = _generate(workspace, job, owner)
    response = _rename(client, job, 'Owner-CV-Accenture-GenAI.tex')
    assert response.status_code == 200, response.data
    cv_dir = Path(saved['cv_tex']).parent
    assert response.data['renamed'] == {saved['cv_tex']: str(cv_dir/'Owner-CV-Accenture-GenAI.tex'), saved['cv_pdf']: str(cv_dir/'Owner-CV-Accenture-GenAI.pdf')}
    assert not Path(saved['cv_tex']).exists() and not Path(saved['cv_pdf']).exists()
    letter = _rename(client, job, 'Anschreiben Accenture', 'letter')
    assert letter.status_code == 200, letter.data
    preview = client.get(f'/api/jobs/{job.id}/cv-generation/').data
    assert preview['artifacts']['cv_tex'] == str(cv_dir/'Owner-CV-Accenture-GenAI.tex')
    assert preview['artifacts']['cv_pdf'] == str(cv_dir/'Owner-CV-Accenture-GenAI.pdf')
    letter_dir = Path(saved['letter_tex']).parent
    assert preview['letter_artifacts']['anschreiben'] == {'letter_tex': str(letter_dir/'Anschreiben Accenture.tex'), 'letter_pdf': str(letter_dir/'Anschreiben Accenture.pdf')}
    # Copy TeX reads the renamed file.
    assert preview['clipboard_tex'] == (cv_dir/'Owner-CV-Accenture-GenAI.tex').read_text(encoding='utf-8')


@pytest.mark.parametrize('name', ['', '   ', '.tex', 'a/b', 'a\\b', 'a:b', 'a*b', 'a?b', 'a"b', 'a<b', 'a>b', 'a|b', 'tab\there', 'CON', 'nul.tex', 'com1', 'ends.', 'x' * 151])
def test_invalid_names_are_refused_and_nothing_moves(client, owner, workspace, monkeypatch, name):
    job = _job(owner); saved = _generate(workspace, job, owner)
    before = sorted(path.name for path in workspace.rglob('*') if path.is_file())
    attempts = []
    monkeypatch.setattr(Path, 'rename', lambda self, target: attempts.append(target))
    response = _rename(client, job, name)
    # Refused by the server's own validation, not by whatever the filesystem happens to reject.
    assert response.status_code == 400 and response.data['detail'] and attempts == []
    assert sorted(path.name for path in workspace.rglob('*') if path.is_file()) == before
    assert latest_generated_sources(job, owner, 'anschreiben')[0] == saved['cv_tex']


def test_typed_pdf_extension_is_normalized(client, owner, workspace):
    job = _job(owner); saved = _generate(workspace, job, owner)
    assert _rename(client, job, '  Fresh-Name.PDF ').status_code == 200
    assert latest_generated_artifacts(job, owner, 'anschreiben')['cv_tex'] == str(Path(saved['cv_tex']).with_name('Fresh-Name.tex'))


# A differently-cased name is the same file only on a case-insensitive filesystem (Windows, where generation runs).
@pytest.mark.parametrize('taken', ['Taken.tex', 'Taken.pdf', pytest.param('taken.PDF', marks=pytest.mark.skipif(os.name != 'nt', reason='case-insensitive filesystem only'))])
def test_renaming_onto_an_existing_file_is_refused_and_overwrites_nothing(client, owner, workspace, taken):
    job = _job(owner); saved = _generate(workspace, job, owner)
    occupied = Path(saved['cv_tex']).parent/taken
    occupied.write_text('someone else', encoding='utf-8')
    names = {path.name for path in occupied.parent.iterdir()}
    response = _rename(client, job, 'Taken')
    assert response.status_code == 409 and 'already exists' in response.data['detail']
    assert occupied.read_text(encoding='utf-8') == 'someone else'
    assert {path.name for path in occupied.parent.iterdir()} == names
    assert Path(saved['cv_tex']).exists() and Path(saved['cv_pdf']).exists()


def test_a_failed_pdf_rename_rolls_the_tex_back(client, owner, workspace, monkeypatch):
    job = _job(owner); saved = _generate(workspace, job, owner)
    real_rename = Path.rename
    def failing(self, target):
        if self.suffix == '.pdf':
            raise PermissionError(13, 'The file is open in another program')
        return real_rename(self, target)
    monkeypatch.setattr(Path, 'rename', failing)
    response = _rename(client, job, 'Locked')
    monkeypatch.setattr(Path, 'rename', real_rename)
    assert response.status_code == 400 and 'open in another program' in response.data['detail']
    assert Path(saved['cv_tex']).exists() and Path(saved['cv_pdf']).exists()
    assert not list(Path(saved['cv_tex']).parent.glob('Locked.*'))
    assert latest_generated_sources(job, owner, 'anschreiben')[0] == saved['cv_tex']


def test_rename_of_a_file_found_only_by_its_legacy_name_is_tracked_afterwards(client, owner, workspace):
    job = _job(owner)
    cv_dir = workspace/'CVs'; cv_dir.mkdir()
    legacy = cv_dir/_target_names(job, applicant_name(owner))[0]
    legacy.write_text('legacy cv', encoding='utf-8'); legacy.with_suffix('.pdf').write_bytes(b'%PDF')
    assert latest_generated_sources(job, owner, 'anschreiben')[0] == str(legacy)
    assert _rename(client, job, 'Hand-Named').status_code == 200
    assert latest_generated_sources(job, owner, 'anschreiben')[0] == str(cv_dir/'Hand-Named.tex')


def test_renaming_updates_a_finished_tasks_paths_zip_and_copy_text(client, owner, workspace):
    job = _job(owner); saved = _generate(workspace, job, owner)
    archive = BytesIO()
    with zipfile.ZipFile(archive, 'w') as bundle:
        for key in ('cv_tex', 'cv_pdf'):
            bundle.write(saved[key], Path(saved[key]).name)
    cv_tasks._tasks['t271'] = {'id': 't271', 'user_id': owner.id, 'job_id': job.id, 'status': 'ready', 'archive': archive.getvalue(), 'filename': 'a.zip',
                               'artifacts': dict(saved), 'clipboard_tex': 'stale'}
    try:
        assert _rename(client, job, 'Task-Renamed').status_code == 200
        task = cv_tasks._tasks['t271']
        assert task['artifacts']['cv_tex'].endswith('Task-Renamed.tex') and task['artifacts']['cv_pdf'].endswith('Task-Renamed.pdf')
        assert sorted(zipfile.ZipFile(BytesIO(task['archive'])).namelist()) == ['Task-Renamed.pdf', 'Task-Renamed.tex']
        assert '% ===== Task-Renamed.tex =====' in task['clipboard_tex']
    finally:
        cv_tasks._tasks.pop('t271', None)


# --- AC3: Explorer rename -------------------------------------------------------------------------

def test_tex_and_pdf_renamed_in_explorer_are_found_by_content(client, owner, workspace):
    job = _job(owner); saved = _generate(workspace, job, owner)
    cv_dir = Path(saved['cv_tex']).parent
    Path(saved['cv_tex']).rename(cv_dir/'Explorer-Name.tex'); Path(saved['cv_pdf']).rename(cv_dir/'Explorer-Name.pdf')
    preview = client.get(f'/api/jobs/{job.id}/cv-generation/').data
    assert preview['artifacts']['cv_tex'] == str(cv_dir/'Explorer-Name.tex') and preview['artifacts']['cv_pdf'] == str(cv_dir/'Explorer-Name.pdf')
    # The tracking itself was updated, not only this one answer.
    sidecar = json.loads(next((workspace/'.dachapply-artifacts').glob('*.json')).read_text(encoding='utf-8'))
    assert sidecar['artifacts'] == {'cv_tex': str(cv_dir/'Explorer-Name.tex'), 'cv_pdf': str(cv_dir/'Explorer-Name.pdf')}
    assert sidecar['names']['cv'] == 'Explorer-Name'


def test_tex_renamed_alone_brings_its_old_named_pdf_along(owner, workspace):
    job = _job(owner); saved = _generate(workspace, job, owner)
    letter_dir = Path(saved['letter_tex']).parent
    Path(saved['letter_tex']).rename(letter_dir/'Only-Tex.tex')
    assert latest_generated_artifacts(job, owner, 'anschreiben') == {
        'cv_tex': saved['cv_tex'], 'cv_pdf': saved['cv_pdf'],
        'letter_tex': str(letter_dir/'Only-Tex.tex'), 'letter_pdf': str(letter_dir/'Only-Tex.pdf')}
    assert not Path(saved['letter_pdf']).exists()


def test_pdf_renamed_alone_is_matched_and_its_tex_follows(owner, workspace):
    # The owner's real case: a renamed PDF beside a TeX that kept the old name.
    job = _job(owner); saved = _generate(workspace, job, owner)
    cv_dir = Path(saved['cv_tex']).parent
    Path(saved['cv_pdf']).rename(cv_dir/'Owner-Accenture-AI-Engineer-For-Generative-AI.pdf')
    assert latest_generated_artifacts(job, owner, 'anschreiben')['cv_pdf'] == str(cv_dir/'Owner-Accenture-AI-Engineer-For-Generative-AI.pdf')
    assert latest_generated_sources(job, owner, 'anschreiben')[0] == str(cv_dir/'Owner-Accenture-AI-Engineer-For-Generative-AI.tex')
    assert not Path(saved['cv_tex']).exists()


def test_a_file_edited_and_recompiled_in_place_is_still_found_after_a_rename(owner, workspace, monkeypatch):
    job = _job(owner); saved = _generate(workspace, job, owner)
    monkeypatch.setattr(cv_generator, 'user_photo', lambda user: None)
    monkeypatch.setattr(cv_generator, '_compile_pdf', lambda output, filename, *a, **k: (output/Path(filename).with_suffix('.pdf')).write_bytes(b'recompiled'))
    source_cv, source_letter = latest_generated_sources(job, owner, 'anschreiben')
    cv_generator.recompile_generated_package(job, 'en', source_cv, source_letter, user_id=owner.id, source_updates={source_cv: 'edited cv'})
    latest_generated_sources(job, owner, 'anschreiben')  # opening the job records the new content
    cv_dir = Path(saved['cv_tex']).parent
    Path(saved['cv_tex']).rename(cv_dir/'After-Edit.tex')
    assert latest_generated_sources(job, owner, 'anschreiben')[0] == str(cv_dir/'After-Edit.tex')


def test_another_jobs_file_with_the_same_content_is_never_adopted(owner, workspace):
    job = _job(owner); other = _job(owner, company='Other')
    mine = _generate(workspace, job, owner, content='identical body')
    theirs = _generate(workspace, other, owner, content='identical body')
    stranger = User.objects.create_user('stranger')
    strangers_job = _job(stranger, company='Stranger')
    strangers = _generate(workspace, strangers_job, stranger, content='identical body')
    Path(mine['cv_tex']).unlink()  # gone; the only byte-identical files belong to other jobs
    assert latest_generated_sources(job, owner, 'anschreiben')[0] is None
    assert latest_generated_sources(other, owner, 'anschreiben')[0] == theirs['cv_tex']
    assert latest_generated_sources(strangers_job, stranger, 'anschreiben')[0] == strangers['cv_tex']


# --- AC4: the new name is preferred ---------------------------------------------------------------

@pytest.fixture
def fake_generation(monkeypatch, cv_assets, owner):
    cv_assets(owner)
    tex = '\\documentclass{article}\\begin{document}%s\\end{document}'
    monkeypatch.setattr(cv_generator, 'validate_model_capability', lambda *a, **k: {})
    monkeypatch.setattr(cv_generator.shutil, 'which', lambda name: name)
    monkeypatch.setattr(cv_generator, 'run_structured_model', lambda *a, **k: {
        'cv_tex': tex % 'new cv', 'letter_tex': tex % 'new letter', 'changed_files': [], 'main_changes': [],
        'unsupported_requirements_not_claimed': [], 'confirmations': {}})
    monkeypatch.setattr(cv_generator, '_compile_pdf', lambda output, filename, *a, **k: (output/Path(filename).with_suffix('.pdf')).write_bytes(b'%PDF new'))
    def generate(job, **kwargs):
        return cv_generator.generate_cv_package(job, 'profile', 'de', 'anschreiben', True, 'openai', 'gpt-5.5', 'medium', user_id=owner.id, **kwargs)
    return generate


def test_generate_uses_the_renamed_name_and_the_replace_choice_still_decides(client, owner, workspace, fake_generation):
    job = _job(owner); saved = _generate(workspace, job, owner)
    assert _rename(client, job, 'Preferred-CV').status_code == 200
    assert _rename(client, job, 'Preferred-Letter', 'letter').status_code == 200
    cv_dir, letter_dir = Path(saved['cv_tex']).parent, Path(saved['letter_tex']).parent
    archive, _, replaced = fake_generation(job, replace_existing=True)
    assert replaced['cv_tex'] == str(cv_dir/'Preferred-CV.tex') and replaced['letter_tex'] == str(letter_dir/'Preferred-Letter.tex')
    assert 'new cv' in (cv_dir/'Preferred-CV.tex').read_text(encoding='utf-8')
    assert sorted(zipfile.ZipFile(BytesIO(archive)).namelist())[:4] == ['Preferred-CV.pdf', 'Preferred-CV.tex', 'Preferred-Letter.pdf', 'Preferred-Letter.tex']
    _, _, kept = fake_generation(job)
    assert kept['cv_tex'] == str(cv_dir/'Preferred-CV-2.tex') and kept['letter_tex'] == str(letter_dir/'Preferred-Letter-2.tex')


def test_preference_survives_a_restart_and_an_explorer_rename_sets_it_too(owner, workspace, fake_generation):
    job = _job(owner); saved = _generate(workspace, job, owner)
    cv_dir = Path(saved['cv_tex']).parent
    Path(saved['cv_tex']).rename(cv_dir/'From-Explorer.tex')
    latest_generated_sources(job, owner, 'anschreiben')
    # Nothing in memory: the preference is read back from the sidecar on disk.
    cv_tasks._tasks.clear()
    _, _, result = fake_generation(job, replace_existing=True)
    assert result['cv_tex'] == str(cv_dir/'From-Explorer.tex')


def test_readjust_and_recompile_write_to_the_renamed_files(client, owner, workspace, fake_generation, monkeypatch):
    job = _job(owner); saved = _generate(workspace, job, owner)
    assert _rename(client, job, 'Adjusted').status_code == 200
    cv_dir = Path(saved['cv_tex']).parent
    source_cv, source_letter = latest_generated_sources(job, owner, 'anschreiben')
    assert source_cv == str(cv_dir/'Adjusted.tex')
    _, _, revised = fake_generation(job, source_cv=source_cv, source_letter=source_letter, revision_instructions='tighten')
    assert revised['cv_tex'] == source_cv and 'new cv' in Path(source_cv).read_text(encoding='utf-8')
    monkeypatch.setattr(cv_generator, 'user_photo', lambda user: None)
    archive, _, recompiled = cv_generator.recompile_generated_package(job, 'en', source_cv, None, user_id=owner.id, source_updates={source_cv: 'recompiled cv'})
    assert recompiled == {'cv_tex': source_cv, 'cv_pdf': str(cv_dir/'Adjusted.pdf')}
    assert Path(source_cv).read_text(encoding='utf-8') == 'recompiled cv' and (cv_dir/'Adjusted.pdf').read_bytes() == b'%PDF new'
    assert sorted(zipfile.ZipFile(BytesIO(archive)).namelist()) == ['Adjusted.pdf', 'Adjusted.tex']
    assert sorted(path.name for path in cv_dir.iterdir()) == ['Adjusted.pdf', 'Adjusted.tex']


# --- AC5: sent documents ----------------------------------------------------------------------------

def test_renaming_a_sent_document_keeps_the_pointer_and_it_stays_read_only(client, owner, workspace, monkeypatch, django_capture_on_commit_callbacks):
    job = _job(owner); saved = _generate(workspace, job, owner)
    with django_capture_on_commit_callbacks(execute=True):
        client.patch(f'/api/jobs/{job.id}/', {'status': 'applied'}, format='json')
    assert _rename(client, job, 'Sent-CV').status_code == 200
    renamed = str(Path(saved['cv_tex']).with_name('Sent-CV.tex'))
    assert latest_generated_sources(job, owner, 'anschreiben')[0] == renamed
    sent = _sent_paths(workspace)
    assert cv_generator._is_sent(renamed, sent) and cv_generator._is_sent(str(Path(renamed).with_suffix('.pdf')), sent)
    before = Path(renamed).read_bytes()
    monkeypatch.setattr(cv_generator, 'user_photo', lambda user: None)
    monkeypatch.setattr(cv_generator, '_compile_pdf', lambda output, filename, *a, **k: (output/Path(filename).with_suffix('.pdf')).write_bytes(b'x'))
    _, _, written = cv_generator.recompile_generated_package(job, 'en', renamed, None, user_id=owner.id, source_updates={renamed: 'changed'})
    assert Path(renamed).read_bytes() == before and written['cv_tex'] == str(Path(renamed).with_name('Sent-CV-2.tex'))


def test_a_sent_document_renamed_in_explorer_keeps_its_read_only_pointer(client, owner, workspace, django_capture_on_commit_callbacks):
    job = _job(owner); saved = _generate(workspace, job, owner)
    with django_capture_on_commit_callbacks(execute=True):
        client.patch(f'/api/jobs/{job.id}/', {'status': 'applied'}, format='json')
    moved = Path(saved['letter_tex']).with_name('Sent-Letter.tex')
    Path(saved['letter_tex']).rename(moved)
    assert latest_generated_sources(job, owner, 'anschreiben')[1] == str(moved)
    assert cv_generator._is_sent(str(moved), _sent_paths(workspace))
