"""TASK-280.3: review, keep, adjust and finalize a prepared application package.
TASK-299: the board's preparation-progress endpoint.

Hermetic, on test_application_prep's fixtures: the fake generator writes each variant's TeX/PDF; the
independent-adjustment test runs the real generator with test_cv_assets' fake model CLI and pdflatex.
"""
import hashlib
import io
import zipfile
from pathlib import Path

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from jobradar.models import JobLead
from jobradar.services import application_prep, cv_generator, cv_tasks
from jobradar.tests.test_application_prep import _job, _move, _req, _state, client, generator, owner, workspace  # noqa: F401 -- fixtures
from jobradar.tests.test_cv_assets import GENERATED, VALID_TEX, _fake_pdflatex

URL = 'https://jobs.example.test/acme/123'


@pytest.fixture
def prepared(client, owner, generator, django_capture_on_commit_callbacks):
    """A To-apply job with cv/letter in EN and DE prepared (mixed language, cover letter required)."""
    job = _job(owner)
    JobLead.objects.filter(pk=job.pk).update(url=URL)
    job.refresh_from_db()
    _move(client, job, 'to_apply', django_capture_on_commit_callbacks)
    variants, _ = _state(client, job)
    assert set(variants) == {'cv-en', 'cv-de', 'letter-en', 'letter-de'}
    return job


def _review(client, job, **body):
    return client.post(f'/api/jobs/{job.id}/application-prep/review/', body, format='json')


def _status(job):
    job.refresh_from_db()
    return job.status


def _hashes(variants):
    return {path: hashlib.sha256(Path(path).read_bytes()).hexdigest() for variant in variants.values() for path in variant['files'].values()}


# --- AC2/AC5: selection and the status it (alone) earns -----------------------------------------

def test_drafts_stay_drafts_until_a_complete_package_is_selected(client, prepared):
    variants, payload = _state(client, prepared)
    assert payload['selection'] == [] and {variant['review'] for variant in variants.values()} == {''}
    assert _status(prepared) == 'to_apply'

    response = _review(client, prepared, action='select', keys=['cv-de', 'letter-de'])
    assert response.status_code == 200, response.json()
    assert response.json()['selection'] == ['cv-de', 'letter-de']
    variants = {variant['key']: variant for variant in response.json()['variants']}
    assert variants['cv-de']['selected'] and variants['cv-de']['review'] == 'keep' and not variants['cv-en']['selected']
    assert _status(prepared) == 'ready_to_submit'

    assert _review(client, prepared, action='clear').status_code == 200
    assert _status(prepared) == 'to_apply'


@pytest.mark.parametrize('keys,needle', [
    (['cv-de'], 'requires a full letter'),          # the posting requires a cover letter
    (['cv-de', 'letter-en'], 'same language'),
    (['cv-de', 'cv-en', 'letter-de'], 'exactly one CV'),
    (['letter-de'], 'exactly one CV'),
    (['cv-de', 'letter-de', 'letter-de'], 'Choose the documents'),
    (['cv-de', 'nope'], 'ready'),
])
def test_an_incoherent_or_incomplete_package_is_refused(client, prepared, keys, needle):
    response = _review(client, prepared, action='select', keys=keys)
    assert response.status_code == 400 and needle in response.json()['detail']
    assert _state(client, prepared)[1]['selection'] == [] and _status(prepared) == 'to_apply'


def test_generation_or_readjustment_never_promotes_a_prepared_job(client, owner, prepared, generator):
    # TASK-265 marks a job Ready after any generation; a job with prepared drafts waits for the owner.
    cv_tasks.start_cv_task(prepared.id, owner.pk, 'ctx', 'de', '', False, 'openai', 'gpt-6.1', 'xhigh', 'normal', auto_clipboard=False)
    assert generator['calls'][-1]['key'] == 'cv-de' and _status(prepared) == 'to_apply'


def test_a_job_without_prepared_drafts_still_follows_task_265(owner, generator):
    job = _job(owner, 'to_apply')
    cv_tasks.start_cv_task(job.id, owner.pk, 'ctx', 'de', '', False, 'openai', 'gpt-6.1', 'xhigh', 'normal', auto_clipboard=False)
    assert _status(job) == 'ready_to_submit'


@pytest.mark.parametrize('status', ['applied', 'interview', 'offer', 'accepted', 'rejected', 'withdrawn', 'archived'])
def test_applied_and_later_statuses_are_never_changed(client, prepared, status):
    JobLead.objects.filter(pk=prepared.pk).update(status=status)
    assert _review(client, prepared, action='select', keys=['cv-en', 'letter-en']).status_code == 200
    assert _status(prepared) == status
    assert _review(client, prepared, action='clear').status_code == 200
    assert _status(prepared) == status
    _review(client, prepared, action='select', keys=['cv-en', 'letter-en'])
    Path(_state(client, prepared)[0]['cv-en']['files']['cv_pdf']).unlink()   # stale invalidation too
    assert _state(client, prepared)[1]['invalidated'] and _status(prepared) == status


# --- AC2: keep / discard / restore ---------------------------------------------------------------

def test_discard_keeps_the_files_and_restore_works_only_while_they_exist(client, prepared):
    before = _hashes(_state(client, prepared)[0])
    assert _review(client, prepared, action='discard', key='letter-en').status_code == 200
    variants, _ = _state(client, prepared)
    assert variants['letter-en']['review'] == 'discard' and _hashes(variants) == before   # nothing deleted
    assert 'discarded' in _review(client, prepared, action='select', keys=['cv-en', 'letter-en']).json()['detail']
    assert _review(client, prepared, action='restore', key='letter-en').status_code == 200
    assert _state(client, prepared)[0]['letter-en']['review'] == 'keep'

    assert _review(client, prepared, action='discard', key='letter-en').status_code == 200
    Path(variants['letter-en']['files']['letter_tex']).unlink()
    response = _review(client, prepared, action='restore', key='letter-en')
    assert response.status_code == 400 and 'no files on disk' in response.json()['detail']
    assert _state(client, prepared)[0]['letter-en']['review'] == 'discard'


def test_retry_skips_a_discarded_failed_variant(client, owner, generator, django_capture_on_commit_callbacks):
    generator['fail'] = {'letter-de'}
    job = _job(owner)
    _move(client, job, 'to_apply', django_capture_on_commit_callbacks)
    generator['fail'] = set(); generator['calls'].clear()
    _review(client, job, action='discard', key='letter-de')
    client.post(f'/api/jobs/{job.id}/application-prep/retry/')
    assert generator['calls'] == []


# --- AC6: stale selections, restart -------------------------------------------------------------

@pytest.mark.parametrize('how', ['delete', 'rename'])
def test_a_selection_whose_file_disappears_is_invalidated_visibly(client, prepared, how):
    _review(client, prepared, action='select', keys=['cv-de', 'letter-de'])
    pdf = Path(_state(client, prepared)[0]['letter-de']['files']['letter_pdf'])
    if how == 'delete':
        pdf.unlink()
    else:
        pdf.rename(pdf.with_name('renamed-in-explorer.pdf'))
    variants, payload = _state(client, prepared)
    assert payload['selection'] == [] and pdf.name in payload['invalidated'] and 'Select a package again' in payload['invalidated']
    assert not variants['letter-de']['selected'] and variants['letter-de']['missing']
    assert _status(prepared) == 'to_apply'
    response = client.get(f'/api/jobs/{prepared.id}/application-prep/export/')
    assert response.status_code == 400 and pdf.name in response.json()['detail']


def test_discarding_a_selected_variant_invalidates_the_package(client, prepared):
    _review(client, prepared, action='select', keys=['cv-de', 'letter-de'])
    payload = _review(client, prepared, action='discard', key='cv-de').json()
    assert payload['selection'] == [] and 'discarded' in payload['invalidated'] and _status(prepared) == 'to_apply'


def test_selection_and_review_survive_a_server_restart(client, prepared):
    _review(client, prepared, action='discard', key='cv-en')
    _review(client, prepared, action='select', keys=['cv-de', 'letter-de'])
    cv_tasks._tasks.clear()   # what a restart loses: every in-memory task
    variants, payload = _state(client, prepared)
    assert payload['selection'] == ['cv-de', 'letter-de'] and variants['cv-en']['review'] == 'discard'
    assert _status(prepared) == 'ready_to_submit'


# --- AC3: independent adjustment ----------------------------------------------------------------

@pytest.mark.parametrize('key', ['cv-de', 'letter-de'])
def test_adjusting_one_variant_leaves_every_other_byte_identical(client, prepared, monkeypatch, key):
    variants, _ = _state(client, prepared)
    before = _hashes(variants)
    # The real revision path, with a fake model CLI and pdflatex. Without a cancel callback _run_command
    # uses subprocess.run, which is what _fake_pdflatex replaces (a task's Popen path is not faked).
    real = cv_generator.generate_cv_package
    monkeypatch.setattr(cv_tasks, 'generate_cv_package', lambda *args, **kwargs: real(*args, **{**kwargs, 'cancelled': None}))
    adjusted = VALID_TEX.replace('tailored', 'adjusted')
    _fake_pdflatex(monkeypatch, {**GENERATED, 'cv_tex': adjusted, 'letter_tex': adjusted})
    response = client.post(f'/api/jobs/{prepared.id}/application-prep/adjust/', {
        'key': key, 'instructions': 'Shorten the summary.', 'provider': 'openai', 'model': 'gpt-5.5', 'effort': 'medium'}, format='json')
    assert response.status_code == 202, response.json()
    after_variants, _ = _state(client, prepared)
    after = _hashes(after_variants)
    mine = set(variants[key]['files'].values())
    assert after_variants[key]['files'] == variants[key]['files'] and not after_variants[key].get('adjust_error')
    assert Path(variants[key]['files'][f"{key.split('-')[0]}_tex"]).read_text(encoding='utf-8') == adjusted
    assert {path: digest for path, digest in after.items() if path not in mine} == {path: digest for path, digest in before.items() if path not in mine}
    assert any(after[path] != before[path] for path in mine)
    assert _status(prepared) == 'to_apply'


def test_a_failed_adjustment_keeps_the_variant_and_its_files(client, prepared, generator):
    before = _hashes(_state(client, prepared)[0])
    generator['fail'] = {'cv-de'}
    assert client.post(f'/api/jobs/{prepared.id}/application-prep/adjust/', {'key': 'cv-de', 'instructions': 'x'}, format='json').status_code == 202
    variants, _ = _state(client, prepared)
    assert variants['cv-de']['status'] == 'ready' and 'cv-de failed' in variants['cv-de']['adjust_error'] and _hashes(variants) == before


def test_a_discarded_variant_cannot_be_adjusted(client, prepared):
    _review(client, prepared, action='discard', key='cv-de')
    response = client.post(f'/api/jobs/{prepared.id}/application-prep/adjust/', {'key': 'cv-de', 'instructions': 'x'}, format='json')
    assert response.status_code == 400 and 'Restore it first' in response.json()['detail']


# --- AC1/AC4: preview, copy, download -----------------------------------------------------------

def test_copy_and_download_carry_the_posting_link_and_meaningful_names(client, prepared):
    export = f'/api/jobs/{prepared.id}/application-prep/export/'
    assert client.get(export).status_code == 400   # no package selected yet
    copied = client.get(export, {'key': 'letter-de', 'as': 'tex'}).json()['text']
    assert copied.startswith(f'% Job listing: {URL}\n')

    _review(client, prepared, action='select', keys=['cv-de', 'letter-de'])
    package = client.get(export, {'as': 'tex'}).json()['text']
    assert package.startswith(f'% Job listing: {URL}') and package.count('% =====') == 2
    response = client.get(export)
    assert response.status_code == 200 and response['Content-Disposition'].endswith('-DE.zip"')
    names = zipfile.ZipFile(io.BytesIO(response.content)).namelist()
    assert len([name for name in names if name.endswith(('.tex', '.pdf'))]) == 4
    assert all(name.endswith(('-DE.tex', '-DE.pdf')) for name in names if name != 'Original-Posting.url')
    assert URL in zipfile.ZipFile(io.BytesIO(response.content)).read('Original-Posting.url').decode()

    pdf = client.get(export, {'key': 'cv-de', 'as': 'pdf'})
    assert pdf.status_code == 200 and pdf['Content-Type'] == 'application/pdf' and pdf['Content-Disposition'].startswith('inline')


def test_export_name_adds_the_language_only_when_missing():
    variant = {'language': 'de'}
    assert application_prep.export_name(variant, 'C:/w/Me-CV-Acme.tex') == 'Me-CV-Acme-DE.tex'
    assert application_prep.export_name(variant, 'C:/w/Me-CV-Acme-DE-2.pdf') == 'Me-CV-Acme-DE-2.pdf'


def test_review_endpoints_are_owner_only(prepared):
    stranger = User.objects.create_user('stranger-280-3', password='pw')
    api = APIClient(); api.force_authenticate(stranger)
    for method, path in (('post', 'review/'), ('post', 'adjust/'), ('get', 'export/')):
        assert getattr(api, method)(f'/api/jobs/{prepared.id}/application-prep/{path}').status_code == 404


# --- TASK-299: the board's progress overlay -----------------------------------------------------

def test_active_endpoint_summarises_only_prepared_unapplied_jobs(client, owner, prepared, monkeypatch):
    other = _job(owner, 'to_apply')            # no preparation record: absent
    ready = {'cv-de': {'document': 'cv', 'language': 'de', 'status': 'ready', 'task_id': '', 'files': {}}}
    reviewed, applied = _job(owner, 'reviewed'), _job(owner, 'applied')
    for job in (reviewed, applied):
        application_prep._save(job, owner.pk, lambda prep: prep.update(variants=ready))
    application_prep._save(prepared, owner.pk, lambda prep: (prep['variants']['letter-de'].update(status='running', task_id='live-1'),
                                                             prep['variants']['cv-en'].update(status='running', task_id='live-2'),
                                                             prep['variants']['letter-en'].update(status='running', task_id='gone')))
    live = {'live-1': {'progress': 45, 'estimated_seconds_remaining': 120, 'status': 'running'},
            'live-2': {'progress': 15, 'estimated_seconds_remaining': 300, 'status': 'running'}}
    real = cv_tasks.get_cv_task
    monkeypatch.setattr(cv_tasks, 'get_cv_task', lambda task_id, user_id: live.get(task_id) or real(task_id, user_id))
    response = client.get('/api/jobs/application-prep/active/')
    assert response.status_code == 200
    # Mean progress of the running two; time left is the slowest one's; the restart-interrupted one is failed.
    # TASK-312 AC7: a Reviewed (or New) job's preparation is badged too; Applied or later never.
    assert response.json() == {str(prepared.id): {'running': 2, 'done': 1, 'failed': 1, 'progress': 30, 'eta': 300},
                               str(reviewed.id): {'running': 0, 'done': 1, 'failed': 0, 'progress': 100, 'eta': 0}}
    assert str(other.id) not in response.json() and str(applied.id) not in response.json()


def test_active_endpoint_is_owner_only(prepared):
    stranger = User.objects.create_user('stranger-299', password='pw')
    api = APIClient(); api.force_authenticate(stranger)
    assert api.get('/api/jobs/application-prep/active/').status_code == 404
