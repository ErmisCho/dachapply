"""TASK-348: a wanted full letter is prepared once per stored letter template of its language.

Hermetic like test_application_prep; the queue tests use its `tasks` fixture, so a test ends each task itself.
"""
from pathlib import Path

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from jobradar.models import CvAsset, JobLead, UserProfile
from jobradar.services import application_prep, cv_generator, cv_tasks, processing_control
from jobradar.tests.test_application_prep import POSTING, _job, _req, _state, client, generator, owner, workspace  # noqa: F401 -- fixtures
from jobradar.tests.test_application_prep_queue import ACTION, QUEUE, tasks  # noqa: F401 -- fixture
from jobradar.tests.test_cv_assets import GENERATED, VALID_TEX, _fake_pdflatex

GERMAN = ['letter-de', 'letter-de-bewerbungsschreiben', 'letter-de-motivationsschreiben']  # templates come in key order
EVERY = ['cv-de', *GERMAN]


def _german(owner, status='to_apply', **extra):
    return _job(owner, status, requirements=_req('de', cover_letter='required'), **extra)


def _variants(job, owner):
    return application_prep._state(job, owner)['variants']


def _summary(client):
    return client.get(QUEUE).json()['summary']


# --- AC1: every applicable letter ---------------------------------------------------------------

def test_a_wanted_letter_gets_one_variant_per_template_with_the_guess_recommended(owner, generator):
    job = _german(owner)
    application_prep.prepare(job.id, owner)
    variants = _variants(job, owner)
    assert list(variants) == EVERY
    assert [(variants[key]['letter_template'], variants[key]['letter_label'], variants[key]['recommended']) for key in GERMAN] == [
        ('anschreiben', 'Anschreiben', True), ('bewerbungsschreiben', 'Bewerbungsschreiben', False), ('motivationsschreiben', 'Motivationsschreiben', False)]
    # One run: each letter once from its own template, and the CV once, not once per letter.
    assert sorted(call['letter_key'] for call in generator['calls'] if call['key'] == 'letter-de') == ['anschreiben', 'bewerbungsschreiben', 'motivationsschreiben']
    assert [call['key'] for call in generator['calls']].count('cv-de') == 1


def test_the_recommendation_follows_the_requested_letter_type(owner, generator):
    job = _job(owner, 'to_apply', requirements=_req('de', motivation_letter='required'))
    application_prep.prepare(job.id, owner)
    assert _variants(job, owner)['letter-de']['letter_template'] == 'motivationsschreiben'
    assert sorted(_variants(job, owner)) == sorted(['cv-de', 'letter-de', 'letter-de-anschreiben', 'letter-de-bewerbungsschreiben'])


def test_a_single_template_language_stays_one_letter_under_its_key(owner, generator):
    job = _job(owner, 'to_apply', requirements=_req('en', cover_letter='required'))
    application_prep.prepare(job.id, owner)
    variants = _variants(job, owner)
    assert list(variants) == ['cv-en', 'letter-en']
    assert variants['letter-en']['recommended'] is True and variants['letter-en']['letter_label'] == 'English motivation letter'


def test_no_letter_wanted_still_means_no_letter_and_a_message_stays_one(owner, generator):
    none, message = _job(owner, 'to_apply', requirements=_req('de')), _job(owner, 'to_apply', requirements=_req('de', short_message='required'))
    application_prep.prepare(none.id, owner)
    application_prep.prepare(message.id, owner)
    assert list(_variants(none, owner)) == ['cv-de']
    assert list(_variants(message, owner)) == ['cv-de', 'message-de']
    assert application_prep._label(_variants(message, owner)['message-de']) == 'Short message · German'


# --- files must not collide ---------------------------------------------------------------------

def _real_generator(monkeypatch):
    monkeypatch.setattr(cv_tasks, 'generate_cv_package', cv_generator.generate_cv_package)
    _fake_pdflatex(monkeypatch, {**GENERATED, 'letter_tex': VALID_TEX})
    monkeypatch.setattr(application_prep, 'available_model_options', cv_generator.available_model_options)
    # A task passes its cancel check, so the model runs through Popen, which _fake_pdflatex does not fake.
    monkeypatch.setattr(cv_generator, '_run_command', lambda command, cancelled=None, **kwargs: cv_generator.subprocess.run(command, **kwargs))


@pytest.mark.parametrize('cache', [False, True])
def test_every_letter_gets_its_own_files_from_the_real_generator(owner, generator, monkeypatch, settings, cache):
    settings.CODEX_CV_CACHE = cache
    _real_generator(monkeypatch)
    job = _german(owner)
    application_prep.prepare(job.id, owner)
    variants = _variants(job, owner)
    assert {variant['status'] for variant in variants.values()} == {'ready'}, [variant['error'] for variant in variants.values()]
    names = [Path(variants[key]['files']['letter_tex']).name for key in GERMAN]
    # The recommended letter keeps today's name; the label alone already separates the others.
    assert names == [f'Prep-Owner-{label}-Acme-Python-Engineer.tex' for label in ('Anschreiben', 'Bewerbungsschreiben', 'Motivationsschreiben')]
    assert len({file for variant in variants.values() for file in variant['files'].values()}) == 8


def test_two_templates_with_one_label_get_distinct_files(owner, generator, monkeypatch):
    CvAsset.objects.filter(user=owner, kind=CvAsset.KIND_LETTER, language='de').update(label='Letter')
    _real_generator(monkeypatch)
    job = _german(owner)
    application_prep.prepare(job.id, owner)
    variants = _variants(job, owner)
    names = {key: Path(variants[key]['files']['letter_tex']).name for key in GERMAN}
    assert '-2' not in ''.join(names.values()), names  # told apart by name, not by the racy free-name check
    assert names['letter-de'] == 'Prep-Owner-Letter-Acme-Python-Engineer.tex'
    assert names['letter-de-bewerbungsschreiben'] == 'Prep-Owner-Letter-Acme-Python-Engineer-Bewerbungsschreiben.tex'


def test_a_multi_language_job_keeps_its_language_suffix_on_every_letter(owner, generator):
    job = _job(owner, 'to_apply')  # mixed posting, a cover letter required: EN and DE
    application_prep.prepare(job.id, owner)
    variants = _variants(job, owner)
    assert list(variants) == ['cv-en', 'cv-de', 'letter-en', *GERMAN]
    assert {key: application_prep._name_suffix(variants[key], variants) for key in ('letter-en', 'letter-de', GERMAN[1])} == {'letter-en': 'EN', 'letter-de': 'DE', GERMAN[1]: 'DE'}
    CvAsset.objects.filter(user=owner, language='de', kind=CvAsset.KIND_LETTER).update(label='Letter')
    for variant in variants.values():
        if variant['language'] == 'de' and variant['document'] == 'letter':
            variant['letter_label'] = 'Letter'
    assert application_prep._name_suffix(variants[GERMAN[1]], variants) == 'Bewerbungsschreiben-DE'


# --- AC5: one failure, the rest usable, retry ------------------------------------------------------

def test_one_failing_letter_leaves_the_others_and_retry_reruns_only_it(owner, client, tasks):
    job = _german(owner)
    application_prep.prepare(job.id, owner)
    tasks['end']('task-1', artifacts={'cv_tex': 'C:/w/cv.tex'})
    tasks['end']('task-2', status='failed')  # the recommended letter
    tasks['end']('task-3', artifacts={'letter_tex': 'C:/w/m.tex'})
    tasks['end']('task-4', artifacts={'letter_tex': 'C:/w/b.tex'})
    variants, _ = _state(client, job)
    assert variants['letter-de']['status'] == 'failed' and variants['letter-de']['error'] == 'model failed'
    assert variants[GERMAN[1]]['status'] == variants[GERMAN[2]]['status'] == 'ready'

    response = client.post(f'/api/jobs/{job.id}/application-prep/retry/', format='json')
    assert response.status_code == 200 and len(tasks['started']) == 5
    stored = _variants(job, owner)
    assert stored['letter-de']['status'] == 'running' and stored['letter-de']['letter_label'] == 'Anschreiben' and stored['letter-de']['recommended'] is True
    assert stored[GERMAN[1]]['status'] == 'ready'


def test_an_extra_letter_keeps_its_identity_through_a_retry_and_a_queue_retry(owner, client, tasks):
    job = _german(owner)
    application_prep.prepare(job.id, owner)
    for task in ('task-1', 'task-2', 'task-3'):
        tasks['end'](task)
    tasks['end']('task-4', status='failed')  # motivationsschreiben
    assert client.post(f'/api/jobs/{job.id}/application-prep/retry/', format='json').status_code == 200
    extra = _variants(job, owner)[GERMAN[2]]
    assert (extra['letter_template'], extra['letter_label'], extra['recommended'], extra['status']) == ('motivationsschreiben', 'Motivationsschreiben', False, 'running')
    tasks['end']('task-5', status='failed')
    assert client.post(ACTION, {'job_id': job.id, 'key': GERMAN[2], 'action': 'retry'}, format='json').status_code == 200
    assert _variants(job, owner)[GERMAN[2]]['letter_label'] == 'Motivationsschreiben'


# --- AC6: the queue counts each letter once --------------------------------------------------------

def test_queue_rows_and_summary_count_each_letter_once(owner, client, tasks):
    job = _german(owner)
    application_prep.prepare(job.id, owner)
    prep = application_prep._state(job, owner)
    each = {key: application_prep._document_seconds(prep, variant) for key, variant in prep['variants'].items()}
    items = client.get(QUEUE).json()['items']
    assert [(item['status'], item['position'], item['label']) for item in items] == [
        ('running', None, 'CV · German'), ('queued', 1, 'Full letter · German · Anschreiben'),
        ('queued', 2, 'Full letter · German · Bewerbungsschreiben'), ('queued', 3, 'Full letter · German · Motivationsschreiben')]
    letter = each['letter-de']
    assert [item['eta_seconds'] for item in items] == [90, 90 + letter, 90 + 2 * letter, 90 + 3 * letter]
    assert _summary(client) == {'done': 0, 'total': 4, 'analyses_left': 0, 'documents_left': 4, 'seconds_left': 90 + 3 * letter}

    tasks['end']('task-1', artifacts={'cv_tex': 'C:/w/cv.tex'})
    assert _summary(client) == {'done': 1, 'total': 4, 'analyses_left': 0, 'documents_left': 3, 'seconds_left': 90 + 2 * letter}
    assert [item['position'] for item in client.get(QUEUE).json()['items'] if item['status'] == 'queued'] == [1, 2]

    tasks['end']('task-2', status='failed')
    assert _summary(client) == {'done': 1, 'total': 3, 'analyses_left': 0, 'documents_left': 2, 'seconds_left': 90 + letter}
    tasks['end']('task-3', artifacts={'letter_tex': 'C:/w/m.tex'})
    tasks['end']('task-4', artifacts={'letter_tex': 'C:/w/b.tex'})
    assert _summary(client) == {'done': 3, 'total': 3, 'analyses_left': 0, 'documents_left': 0, 'seconds_left': 0}


def test_the_dashboard_sees_each_letter_as_one_job(owner, tasks):
    job = _german(owner)
    application_prep.prepare(job.id, owner)
    assert [key for *_, key in application_prep._queue] == GERMAN  # dashboard_runtime adds len(_queue) to remaining_jobs
    identities = {processing_control.job_key('documents', {'finish': {'job_id': job.id, 'user_id': owner.pk, 'key': key, 'action': 'finish'}}) for key in EVERY}
    assert len(identities) == 4  # one running unit per letter, never collapsed into one


def test_the_board_badge_counts_every_letter(owner, tasks):
    job = _german(owner)
    application_prep.prepare(job.id, owner)
    assert application_prep.board_summary(job, owner)['running'] == 4


# --- review and package ----------------------------------------------------------------------------

@pytest.fixture
def prepared(owner, generator):
    job = _german(owner)
    application_prep.prepare(job.id, owner)
    return job


def test_the_package_takes_any_one_letter_and_refuses_two(prepared, owner):
    application_prep.review(prepared, owner, 'select', keys=['cv-de', GERMAN[2]])
    prepared.refresh_from_db()
    assert prepared.status == 'ready_to_submit'
    assert application_prep.public_state(prepared, owner)['selection'] == ['cv-de', GERMAN[2]]
    with pytest.raises(ValueError, match='at most one full letter'):
        application_prep.review(prepared, owner, 'select', keys=['cv-de', GERMAN[0], GERMAN[1]])


def test_a_required_letter_may_be_any_of_them_but_not_none(prepared, owner):
    with pytest.raises(ValueError, match='requires a full letter'):
        application_prep.review(prepared, owner, 'select', keys=['cv-de'])


def test_discarding_an_unselected_letter_keeps_the_package(prepared, owner):
    application_prep.review(prepared, owner, 'select', keys=['cv-de', GERMAN[1]])
    application_prep.review(prepared, owner, 'discard', GERMAN[2])
    assert application_prep.public_state(prepared, owner)['selection'] == ['cv-de', GERMAN[1]]


def test_a_redo_requeues_extras_with_their_identity(prepared, owner, tasks):
    assert application_prep._redo(prepared, owner) == 4
    extra = _variants(prepared, owner)[GERMAN[1]]
    assert extra['letter_template'] == 'bewerbungsschreiben' and extra['letter_label'] == 'Bewerbungsschreiben' and extra['recommended'] is False


def test_resume_queue_restores_extra_letters(owner, tasks):
    job = _german(owner)
    application_prep.prepare(job.id, owner)
    application_prep._queue.clear()
    assert application_prep.resume_queue() == 3
    assert [key for *_, key in application_prep._queue] == GERMAN


def test_a_job_prepared_before_this_keeps_working(owner, client, generator):
    job = _german(owner)
    tex = Path(application_prep.settings.CODEX_CV_WORKSPACE) / 'output' / 'old.tex'
    tex.write_text('old letter', encoding='utf-8'); tex.with_suffix('.pdf').write_bytes(b'%PDF')
    cv = tex.with_name('old-cv.tex'); cv.write_text('old cv', encoding='utf-8'); cv.with_suffix('.pdf').write_bytes(b'%PDF')
    application_prep._save(job, owner.pk, lambda prep: prep.update(model={}, variants={
        'cv-de': {'document': 'cv', 'language': 'de', 'letter_template': '', 'status': 'ready', 'task_id': '', 'error': '', 'files': {'cv_tex': str(cv), 'cv_pdf': str(cv.with_suffix('.pdf'))}},
        'letter-de': {'document': 'letter', 'language': 'de', 'letter_template': 'anschreiben', 'status': 'ready', 'task_id': '', 'error': '', 'files': {'letter_tex': str(tex), 'letter_pdf': str(tex.with_suffix('.pdf'))}}}))
    assert list(_state(client, job)[0]) == ['cv-de', 'letter-de']  # no extras appear on an old job
    application_prep.prepare(job.id, owner, retry=True)
    assert list(_state(client, job)[0]) == ['cv-de', 'letter-de'] and generator['calls'] == []
    assert application_prep._label(_variants(job, owner)['letter-de']) == 'Full letter · German'
    assert client.get(f'/api/jobs/{job.id}/application-prep/export/?as=tex&key=letter-de').json() == {'text': 'old letter'}
    application_prep.review(job, owner, 'select', keys=['cv-de', 'letter-de'])
    job.refresh_from_db()
    assert job.status == 'ready_to_submit'


# --- AC3/AC4: copying one file through the export endpoint -----------------------------------------------------------------------

def _tex(client, job, key):
    return client.get(f'/api/jobs/{job.id}/application-prep/export/', {'as': 'tex', 'key': key})


def test_the_endpoint_returns_only_the_chosen_file_with_the_job_link(prepared, owner, client):
    JobLead.objects.filter(pk=prepared.pk).update(url='https://example.test/job')
    variants = _variants(prepared, owner)
    for key in GERMAN:
        response = _tex(client, prepared, key)
        body = Path(variants[key]['files']['letter_tex']).read_text(encoding='utf-8')
        assert response.status_code == 200 and response.json() == {'text': f'% Job listing: https://example.test/job\n\n{body}'}
    assert Path(variants['cv-de']['files']['cv_tex']).read_text(encoding='utf-8') in _tex(client, prepared, 'cv-de').json()['text']
    assert len({_tex(client, prepared, key).json()['text'] for key in EVERY}) == 4


def test_reading_tex_generates_nothing_and_writes_nothing(prepared, owner, client, generator):
    calls, before = len(generator['calls']), application_prep._state(prepared, owner)
    for key in GERMAN:
        assert _tex(client, prepared, key).status_code == 200
    assert len(generator['calls']) == calls and application_prep._state(prepared, owner) == before


def test_tex_never_rides_on_the_polled_state(prepared, owner, client):
    body = Path(_variants(prepared, owner)['letter-de']['files']['letter_tex']).read_text(encoding='utf-8')
    assert body not in client.get(f'/api/jobs/{prepared.id}/application-prep/').content.decode()


def test_the_endpoint_refuses_unknown_keys_missing_files_and_other_accounts(prepared, owner, client):
    assert _tex(client, prepared, 'letter-de-nope').status_code == 400
    assert _tex(client, prepared, '').status_code == 400
    Path(_variants(prepared, owner)['letter-de']['files']['letter_tex']).unlink()
    assert _tex(client, prepared, 'letter-de').status_code == 400
    assert _tex(client, prepared, GERMAN[1]).status_code == 200

    other = User.objects.create_user('other-owner', password='pw')
    UserProfile.objects.update_or_create(user=other, defaults={'can_generate_cv': True})
    stranger, plain = APIClient(), APIClient()
    stranger.force_authenticate(other)
    plain.force_authenticate(User.objects.create_user('no-cv-account', password='pw'))
    assert _tex(stranger, prepared, GERMAN[1]).status_code == 404
    assert _tex(plain, prepared, GERMAN[1]).status_code == 404
    assert APIClient().get(f'/api/jobs/{prepared.id}/application-prep/export/', {'as': 'tex', 'key': GERMAN[1]}).status_code in (401, 403)


def test_a_failed_letter_has_no_tex(owner, client, tasks):
    job = _german(owner)
    application_prep.prepare(job.id, owner)
    tasks['end']('task-1')
    tasks['end']('task-2', status='failed')
    assert _tex(client, job, 'letter-de').status_code == 400
