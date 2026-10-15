"""TASK-280.2: background document preparation when a job moves into To apply.

Hermetic: no model CLI and no pdflatex run. Integration tests replace cv_tasks.generate_cv_package
and run each variant's worker in-thread (SyncThread), so its writes share this test's transaction;
the real-generator test uses test_cv_assets' fake codex/pdflatex.
"""
import threading
import time
from pathlib import Path

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from jobradar.models import JobLead, UserProfile
from jobradar.services import application_prep, cv_generator, cv_tasks
from jobradar.services.application_prep import plan_variants
from jobradar.services.application_requirements import normalize_application_requirements
from jobradar.tests.test_cv_assets import GENERATED, VALID_TEX, _fake_pdflatex

POSTING = 'We are hiring a Python engineer. Please send your CV and a cover letter. Wir freuen uns auf Ihre Bewerbung.'


def _req(posting='en', application='', **documents):
    return {'posting_language': posting, 'application_language': application, 'application_language_quote': '',
            'documents': [{'type': kind, 'name': '', 'status': status, 'quote': ''} for kind, status in documents.items()],
            'source': 'owner'}


def _keys(requirements):
    return [variant['key'] for variant in plan_variants(requirements)[0]]


# --- the generation matrix (AC2/AC3/AC4) -------------------------------------------------------

def test_clear_instructions_give_one_cv_in_the_application_language_plus_only_wanted_letters():
    # Explicit application language outranks the posting language.
    assert _keys(_req('en', 'de', cover_letter='required')) == ['cv-de', 'letter-de']
    assert _keys(_req('de', '', short_message='preferred')) == ['cv-de', 'message-de']
    # Optional is not required or preferred: not generated.
    assert _keys(_req('en', '', cover_letter='optional')) == ['cv-en']


def test_explicitly_unwanted_letters_are_never_generated():
    assert _keys(_req('en', '', cover_letter='not_accepted')) == ['cv-en']
    # Even when the message requirement is unclear, the unwanted full letter stays out.
    assert _keys(_req('en', '', cover_letter='not_accepted', short_message='unclear')) == ['cv-en', 'message-en']


def test_absent_and_not_mentioned_follow_the_visible_rule_not_required():
    assert _keys(_req('de')) == ['cv-de']
    assert _keys(_req('de', '', cover_letter='not_mentioned', motivation_letter='not_mentioned', short_message='not_mentioned')) == ['cv-de']
    assert 'not prepared automatically' in application_prep.LETTER_RULE


def test_contradictory_instructions_become_unclear_and_give_a_letter_and_a_message():
    job = JobLead(original_source_text=POSTING)
    stored = normalize_application_requirements({'posting_language': 'en', 'documents': [
        {'type': 'cover_letter', 'status': 'required'}, {'type': 'cover_letter', 'status': 'not_accepted'}]}, job, source='owner')
    assert stored['documents'][0]['status'] == 'unclear'
    assert _keys(stored) == ['cv-en', 'letter-en', 'message-en']


def test_mixed_or_unclear_language_gives_bounded_en_and_de_variants():
    assert _keys(_req('mixed')) == ['cv-en', 'cv-de']
    assert _keys(_req('unclear', '', cover_letter='required')) == ['cv-en', 'cv-de', 'letter-en', 'letter-de']
    # The full fallback set: at most CV, full letter and short message per plausible language.
    assert _keys(_req('mixed', '', motivation_letter='unclear')) == ['cv-en', 'cv-de', 'letter-en', 'letter-de', 'message-en', 'message-de']


def test_unclear_letter_in_a_clear_language_stays_in_that_language():
    assert _keys(_req('de', '', cover_letter='unclear')) == ['cv-de', 'letter-de', 'message-de']


def test_not_analysed_starts_nothing():
    variants, reason = plan_variants({})
    assert variants == [] and 'not analysed' in reason


# --- integration through the To-apply transition ----------------------------------------------

class SyncThread:
    def __init__(self, target, args=(), name='', daemon=None):
        self.target, self.args = target, args

    def start(self):
        self.target(*self.args)


@pytest.fixture
def workspace(settings, tmp_path):
    settings.CODEX_CV_WORKSPACE = str(tmp_path); settings.CODEX_CV_ENABLED = True; settings.CODEX_CV_CACHE = False
    settings.CODEX_CV_OPEN_OUTPUT_FOLDER = False
    (tmp_path / 'CVs').mkdir(); (tmp_path / 'output').mkdir()
    return tmp_path


@pytest.fixture
def owner(db, cv_assets):
    user = User.objects.create_user('prep-owner', email='prep@example.test', password='pw')
    UserProfile.objects.update_or_create(user=user, defaults={'can_generate_cv': True})
    cv_assets(user)
    return user


@pytest.fixture
def client(owner):
    api = APIClient(); api.force_authenticate(owner)
    return api


@pytest.fixture
def generator(monkeypatch, workspace):
    """Fake generate_cv_package: writes a TeX/PDF pair per call, fails for keys in `fail`."""
    state = {'calls': [], 'fail': set()}

    def generate(job, profile, cv_key, letter_key, create_letter, provider, model, effort, speed, progress, *args, **kwargs):
        create_cv = args[3]  # (source_cv, source_letter, revision_instructions, create_cv, correction_image)
        document = 'cv' if create_cv else 'message' if kwargs.get('short_message') else 'letter'
        key = f'{document}-{cv_key}'
        state['calls'].append({'key': key, 'provider': provider, 'model': model, 'effort': effort, 'letter_key': letter_key, **kwargs})
        if key in state['fail']:
            raise RuntimeError(f'{key} failed')
        prefix = 'cv' if create_cv else 'letter'
        folder = workspace / ('CVs' if create_cv else 'output')
        tex = cv_generator._unique_destination(folder, f'{key}{kwargs.get("name_suffix", "")}.tex')
        tex.write_text(f'{key} {len(state["calls"])}', encoding='utf-8'); tex.with_suffix('.pdf').write_bytes(b'%PDF')
        return b'zip', 'a.zip', {f'{prefix}_tex': str(tex), f'{prefix}_pdf': str(tex.with_suffix('.pdf'))}

    monkeypatch.setattr(cv_tasks, 'generate_cv_package', generate)
    monkeypatch.setattr(cv_tasks, 'Thread', SyncThread)
    monkeypatch.setattr(cv_tasks, '_copy_to_clipboard', lambda text: pytest.fail('auto preparation must not touch the clipboard'))
    monkeypatch.setattr(application_prep, 'available_model_options', lambda: [
        {'provider': 'anthropic', 'key': 'sonnet', 'efforts': ['medium']},
        {'provider': 'openai', 'key': 'gpt-6.1', 'efforts': ['medium', 'high', 'xhigh'], 'default_effort': 'medium'}])
    monkeypatch.setattr(application_prep, 'validate_model_capability', lambda *a, **k: None)
    return state


def _job(owner, status='reviewed', requirements=None, text=POSTING):
    return JobLead.objects.create(company='ACME', title='Python Engineer', status=status, created_by=owner, original_source_text=text,
                                  application_requirements=_req('mixed', '', cover_letter='required') if requirements is None else requirements)


def _move(client, job, status, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        assert client.patch(f'/api/jobs/{job.id}/', {'status': status}, format='json').status_code == 200


def _state(client, job):
    response = client.get(f'/api/jobs/{job.id}/application-prep/')
    assert response.status_code == 200
    return {variant['key']: variant for variant in response.json()['variants']}, response.json()


def test_transition_into_to_apply_prepares_variants_as_drafts(client, owner, generator, django_capture_on_commit_callbacks):
    job = _job(owner)
    _move(client, job, 'to_apply', django_capture_on_commit_callbacks)
    variants, payload = _state(client, job)
    assert set(variants) == {'cv-en', 'cv-de', 'letter-en', 'letter-de'}
    assert all(variant['status'] == 'ready' and Path(next(iter(variant['files'].values()))).is_file() for variant in variants.values())
    # Default model: the newest Codex at xhigh (draft_chat.default_draft_choice), never the clipboard.
    assert {(call['provider'], call['model'], call['effort']) for call in generator['calls']} == {('openai', 'gpt-6.1', 'xhigh')}
    # EN/DE variants of one job get distinguishable names; German letters use the Anschreiben template.
    assert {call['key']: call.get('name_suffix') for call in generator['calls']}['cv-de'] == 'DE'
    assert variants['letter-de']['letter_template'] == 'anschreiben' and variants['letter-en']['letter_template'] == 'motivation_letter'
    assert payload['model']['model'] == 'gpt-6.1'
    # Drafts are not a chosen package: the job stays To apply (TASK-280 AC4).
    job.refresh_from_db()
    assert job.status == 'to_apply'


@pytest.mark.parametrize('start,target', [('new', 'reviewed'), ('reviewed', 'new'), ('to_apply', 'to_apply'), ('to_apply', 'applied'), ('applied', 'interview')])
def test_only_a_transition_into_to_apply_generates(client, owner, generator, django_capture_on_commit_callbacks, start, target):
    job = _job(owner, start)
    _move(client, job, target, django_capture_on_commit_callbacks)
    assert generator['calls'] == []
    assert _state(client, job)[0] == {}


@pytest.mark.parametrize('status', ['new', 'reviewed', 'applied', 'interview', 'rejected', 'archived'])
def test_prepare_refuses_jobs_outside_to_apply(owner, generator, status):
    job = _job(owner, status)
    application_prep.prepare(job.id, owner)
    application_prep.prepare(job.id, owner, retry=True)
    assert generator['calls'] == []


@pytest.mark.parametrize('text,requirements,needle', [
    ('', None, 'no usable posting text'),
    ('https://example.test/job', None, 'no usable posting text'),
    (POSTING, {}, 'not analysed'),
])
def test_missing_text_or_analysis_starts_nothing_and_says_why(client, owner, generator, django_capture_on_commit_callbacks, text, requirements, needle):
    job = _job(owner, requirements=requirements, text=text)
    _move(client, job, 'to_apply', django_capture_on_commit_callbacks)
    _, payload = _state(client, job)
    assert generator['calls'] == [] and payload['variants'] == [] and needle in payload['reason']


def test_missing_template_starts_nothing(client, owner, generator, django_capture_on_commit_callbacks):
    owner.cv_assets.filter(language='de').delete()
    job = _job(owner)
    _move(client, job, 'to_apply', django_capture_on_commit_callbacks)
    assert generator['calls'] == [] and 'No German CV template' in _state(client, job)[1]['reason']


def test_reentering_to_apply_after_a_skip_tries_again(client, owner, generator, django_capture_on_commit_callbacks):
    job = _job(owner, requirements={})
    _move(client, job, 'to_apply', django_capture_on_commit_callbacks)
    JobLead.objects.filter(pk=job.pk).update(application_requirements=_req('de'))
    _move(client, job, 'reviewed', django_capture_on_commit_callbacks)
    _move(client, job, 'to_apply', django_capture_on_commit_callbacks)
    assert [call['key'] for call in generator['calls']] == ['cv-de']


def test_double_transition_generates_each_variant_once(client, owner, generator, django_capture_on_commit_callbacks):
    # A failed variant included: re-entering To apply is not a retry; only the Retry action is.
    generator['fail'] = {'cv-de'}
    job = _job(owner)
    _move(client, job, 'to_apply', django_capture_on_commit_callbacks)
    generator['fail'] = set()
    _move(client, job, 'reviewed', django_capture_on_commit_callbacks)
    _move(client, job, 'to_apply', django_capture_on_commit_callbacks)
    application_prep.prepare(job.id, owner)
    assert sorted(call['key'] for call in generator['calls']) == ['cv-de', 'cv-en', 'letter-de', 'letter-en']


@pytest.mark.django_db(transaction=True)  # the racing threads need their own connections
def test_concurrent_prepare_calls_start_each_variant_once(owner, workspace, monkeypatch, generator):
    job = _job(owner, 'to_apply')
    started = []

    def slow_start(*args, **kwargs):
        time.sleep(.05)  # widen the window two unsynchronised callers would both slip through
        started.append(kwargs['create_cv'])
        return f'task-{len(started)}'
    monkeypatch.setattr(cv_tasks, 'start_cv_task', slow_start)
    threads = [threading.Thread(target=application_prep.prepare, args=(job.id, owner)) for _ in range(3)]
    for thread in threads: thread.start()
    for thread in threads: thread.join()
    assert len(started) == 4


def test_a_failed_variant_leaves_the_others_and_retry_reruns_only_it(client, owner, generator, django_capture_on_commit_callbacks):
    generator['fail'] = {'letter-de'}
    job = _job(owner)
    _move(client, job, 'to_apply', django_capture_on_commit_callbacks)
    variants, _ = _state(client, job)
    assert variants['letter-de']['status'] == 'failed' and 'letter-de failed' in variants['letter-de']['error']
    good = {key: (variant['files'], {path: Path(path).read_bytes() for path in variant['files'].values()}) for key, variant in variants.items() if key != 'letter-de'}
    assert all(variant['status'] == 'ready' for key, variant in variants.items() if key != 'letter-de')

    generator['fail'] = set(); generator['calls'].clear()
    response = client.post(f'/api/jobs/{job.id}/application-prep/retry/')
    assert response.status_code == 200
    assert [call['key'] for call in generator['calls']] == ['letter-de']
    variants, _ = _state(client, job)
    assert variants['letter-de']['status'] == 'ready'
    for key, (files, contents) in good.items():
        assert variants[key]['files'] == files and all(Path(path).read_bytes() == data for path, data in contents.items())
    # Nothing failed any more: a further retry starts nothing.
    generator['calls'].clear()
    client.post(f'/api/jobs/{job.id}/application-prep/retry/')
    assert generator['calls'] == []


def test_a_run_interrupted_by_a_restart_shows_failed_and_is_retried(client, owner, generator, django_capture_on_commit_callbacks):
    job = _job(owner, requirements=_req('de'))
    _move(client, job, 'to_apply', django_capture_on_commit_callbacks)
    application_prep._save(job, owner.pk, lambda prep: prep['variants']['cv-de'].update(status='running', task_id='gone'))
    variants, _ = _state(client, job)
    assert variants['cv-de']['status'] == 'failed' and 'restarted' in variants['cv-de']['error']
    generator['calls'].clear()
    client.post(f'/api/jobs/{job.id}/application-prep/retry/')
    assert [call['key'] for call in generator['calls']] == ['cv-de'] and _state(client, job)[0]['cv-de']['status'] == 'ready'


def test_existing_generated_files_are_never_joined_or_replaced(client, owner, workspace, generator, django_capture_on_commit_callbacks):
    job = _job(owner, requirements=_req('de'))
    existing = workspace / 'CVs' / 'mine.tex'; existing.write_text('owner edit', encoding='utf-8')
    cv_generator._record_artifact_metadata(job, owner.id, {'cv_tex': str(existing)})
    _move(client, job, 'to_apply', django_capture_on_commit_callbacks)
    assert generator['calls'] == [] and 'already exist' in _state(client, job)[1]['reason']
    assert existing.read_text(encoding='utf-8') == 'owner edit'


def test_a_variant_that_cannot_start_does_not_stop_the_others(owner, generator, monkeypatch):
    job = _job(owner, 'to_apply')
    real = cv_tasks.start_cv_task

    def start(*args, **kwargs):
        if not kwargs['create_cv'] and args[3] == 'en':
            raise RuntimeError('cannot start')
        return real(*args, **kwargs)
    monkeypatch.setattr(cv_tasks, 'start_cv_task', start)
    state = application_prep.prepare(job.id, owner)
    statuses = {variant['key']: variant['status'] for variant in state['variants']}
    assert statuses == {'cv-en': 'ready', 'cv-de': 'ready', 'letter-en': 'failed', 'letter-de': 'ready'}


def test_endpoints_are_owner_only(owner, generator):
    job = _job(owner, 'to_apply')
    stranger = User.objects.create_user('stranger', password='pw')
    api = APIClient(); api.force_authenticate(stranger)
    assert api.get(f'/api/jobs/{job.id}/application-prep/').status_code == 404
    assert api.post(f'/api/jobs/{job.id}/application-prep/retry/').status_code == 404


# --- the real generator: names, prompt, no overwrite --------------------------------------------

def test_short_message_and_language_suffix_reach_the_real_generator_without_overwriting(db, workspace, monkeypatch, cv_assets):
    user = User.objects.create_user('real@example.test')
    cv_assets(user)
    job = JobLead.objects.create(company='Acme', title='Engineer', original_source_text=POSTING, created_by=user)
    _fake_pdflatex(monkeypatch, {**GENERATED, 'letter_tex': VALID_TEX})
    prompts = []
    real_prompt = cv_generator._prompt
    monkeypatch.setattr(cv_generator, '_prompt', lambda *a, **k: prompts.append(real_prompt(*a, **k)) or prompts[-1])

    _, _, letter = cv_generator.generate_cv_package(job, 'profile', 'de', 'anschreiben', True, 'openai', 'gpt-5.5', 'medium', create_cv=False, user_id=user.id, name_suffix='DE')
    _, _, message = cv_generator.generate_cv_package(job, 'profile', 'de', 'anschreiben', True, 'openai', 'gpt-5.5', 'medium', create_cv=False, user_id=user.id, short_message=True, name_suffix='DE')
    assert 'SHORT APPLICATION MESSAGE' not in prompts[0] and 'SHORT APPLICATION MESSAGE' in prompts[1]
    assert Path(letter['letter_tex']).name.endswith('-Anschreiben-Acme-Engineer-DE.tex')
    assert Path(message['letter_tex']).name.endswith('-Short-Message-Acme-Engineer-DE.tex')
    # The short message is tracked apart: the job's current Anschreiben is still the full letter.
    assert cv_generator.latest_generated_sources(job, user, 'anschreiben')[1] == letter['letter_tex']

    before = Path(message['letter_tex']).read_bytes()
    _, _, again = cv_generator.generate_cv_package(job, 'profile', 'de', 'anschreiben', True, 'openai', 'gpt-5.5', 'medium', create_cv=False, user_id=user.id, short_message=True, name_suffix='DE')
    assert again['letter_tex'] != message['letter_tex'] and Path(message['letter_tex']).read_bytes() == before
