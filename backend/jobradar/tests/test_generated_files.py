"""TASK-301: the job's Generated files table lists every document generated for it, from every source."""
from pathlib import Path

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from jobradar.models import JobLead
from jobradar.services import cv_tasks
from jobradar.services.cv_generator import (
    _edit_sidecar, _record_artifact_metadata, delete_generated_metadata, generated_files,
)


@pytest.fixture
def workspace(settings, tmp_path):
    settings.CODEX_CV_WORKSPACE = str(tmp_path)
    settings.CODEX_CV_ENABLED = True
    settings.CODEX_CV_CACHE = False
    settings.CODEX_CV_OWNER_EMAIL = 'owner@example.test'
    (tmp_path/'CVs').mkdir(); (tmp_path/'output').mkdir()
    return tmp_path


@pytest.fixture
def owner(db, cv_assets):
    user = User.objects.create_user('owner', email='owner@example.test', password='pw')
    cv_assets(user)
    return user


def _job(owner):
    return JobLead.objects.create(company='Wienerberger', title='AI Engineer', raw_description='Python', created_by=owner,
                                  original_source_text='Python role with enough original posting text to generate from.')


def _pair(folder, stem):
    tex = folder/f'{stem}.tex'
    tex.write_text(stem, encoding='utf-8'); tex.with_suffix('.pdf').write_bytes(b'%PDF')
    return {'tex': str(tex), 'pdf': str(tex.with_suffix('.pdf'))}


def _rows(job, owner):
    return [(Path(row['tex']).name, row['kind'], row['language'], row['missing']) for row in generated_files(job, owner)]


def test_manual_generations_all_stay_listed_newest_first(owner, workspace):
    # A second generation moves the "current" pointers; the first one's files must not vanish.
    job = _job(owner)
    first_cv, first_letter = _pair(workspace/'CVs', 'Owner-CV-1'), _pair(workspace/'output', 'Owner-Anschreiben-1')
    _record_artifact_metadata(job, owner.pk, {'cv_tex': first_cv['tex'], 'cv_pdf': first_cv['pdf'], 'letter_tex': first_letter['tex'], 'letter_pdf': first_letter['pdf']}, 'anschreiben', 'de')
    second_cv = _pair(workspace/'CVs', 'Owner-CV-2')
    _record_artifact_metadata(job, owner.pk, {'cv_tex': second_cv['tex'], 'cv_pdf': second_cv['pdf']}, '', 'en')
    rows = generated_files(job, owner)
    assert [(Path(row['tex']).name, row['kind'], row['language']) for row in rows] == [
        ('Owner-CV-2.tex', 'cv', 'en'), ('Owner-CV-1.tex', 'cv', 'de'), ('Owner-Anschreiben-1.tex', 'letter', 'de')]
    assert rows[0]['pdf'] == second_cv['pdf'] and rows[0]['generated_at'] >= rows[1]['generated_at'] and not rows[0]['pdf_missing']


def test_preparation_variants_adjustments_and_short_messages_are_listed(owner, workspace):
    # Written the way TASK-280.2 left it before history existed: variant files only under 'preparation'.
    job = _job(owner)
    cv = _pair(workspace/'CVs', 'Owner-CV-Wienerberger-DE')
    letter = _pair(workspace/'output', 'Owner-Anschreiben-Wienerberger')
    message = _pair(workspace/'output', 'Owner-Short-Message-Wienerberger')
    def change(data):
        data['preparation'] = {'variants': {
            'cv-de': {'document': 'cv', 'language': 'de', 'status': 'ready', 'files': {'cv_tex': cv['tex'], 'cv_pdf': cv['pdf']}},
            'letter-de': {'document': 'letter', 'language': 'de', 'letter_template': 'anschreiben', 'status': 'ready', 'files': {'letter_tex': letter['tex'], 'letter_pdf': letter['pdf']}},
            'cv-en': {'document': 'cv', 'language': 'en', 'status': 'failed', 'files': {}},
        }}
        # A short message is tracked under '<letter_key>:short' (TASK-280.2), never the full letter's key.
        data['letters'] = {'anschreiben:short': {'letter_tex': message['tex'], 'letter_pdf': message['pdf']}}
    _edit_sidecar(job, owner.pk, change)
    assert sorted(_rows(job, owner)) == [
        ('Owner-Anschreiben-Wienerberger.tex', 'letter', 'de', False),
        ('Owner-CV-Wienerberger-DE.tex', 'cv', 'de', False),
        ('Owner-Short-Message-Wienerberger.tex', 'message', 'de', False)]
    # TASK-280.3 adjustment: the variant's files are rewritten through the revision path -- same row, not a second one.
    _record_artifact_metadata(job, owner.pk, {'letter_tex': letter['tex'], 'letter_pdf': letter['pdf']}, 'anschreiben', '')
    assert len(generated_files(job, owner)) == 3 and Path(generated_files(job, owner)[0]['tex']).name == 'Owner-Anschreiben-Wienerberger.tex'


def test_a_deleted_file_shows_as_missing_and_listing_survives_restart_and_applied(owner, workspace):
    job = _job(owner)
    cv = _pair(workspace/'CVs', 'Owner-CV')
    letter = _pair(workspace/'output', 'Owner-Anschreiben')
    _record_artifact_metadata(job, owner.pk, {'cv_tex': cv['tex'], 'cv_pdf': cv['pdf']}, '', 'de')
    _record_artifact_metadata(job, owner.pk, {'letter_tex': letter['tex'], 'letter_pdf': letter['pdf']}, 'anschreiben', '')
    Path(cv['tex']).unlink(); Path(cv['pdf']).unlink()
    cv_tasks._tasks.clear()  # a server restart: nothing in memory, only the workspace sidecar
    client = APIClient(); client.force_authenticate(owner)
    listed = client.get(f'/api/jobs/{job.id}/cv-generation/').data['generated_files']
    assert [(Path(row['tex']).name, row['missing'], row['pdf_missing']) for row in listed] == [('Owner-Anschreiben.tex', False, False), ('Owner-CV.tex', True, True)]
    # Applied retires the sidecar; the job keeps its whole list, missing file included.
    delete_generated_metadata(job)
    assert sorted(_rows(job, owner)) == [('Owner-Anschreiben.tex', 'letter', 'de', False), ('Owner-CV.tex', 'cv', 'de', True)]


def test_another_jobs_files_are_not_listed(owner, workspace):
    job, other = _job(owner), _job(owner)
    cv = _pair(workspace/'CVs', 'Owner-CV-Other')
    _record_artifact_metadata(other, owner.pk, {'cv_tex': cv['tex'], 'cv_pdf': cv['pdf']}, '', 'en')
    assert generated_files(job, owner) == [] and len(generated_files(other, owner)) == 1
