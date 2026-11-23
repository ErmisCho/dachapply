"""TASK-405: the owner ticks which of a job's CVs and letters to adjust, recompile or copy as TeX."""
from pathlib import Path
from types import SimpleNamespace

import pytest
from django.contrib.auth.models import User
from django.core.cache import cache
from rest_framework.test import APIClient

from jobradar.models import JobLead
from jobradar.services import cv_generator, cv_tasks
from jobradar.services.cv_generator import _edit_sidecar, _record_artifact_metadata


@pytest.fixture
def env(db, cv_assets, settings, tmp_path, monkeypatch):
    """A job with two CVs, two letters and a short message on disk, and the calls the endpoints make."""
    settings.CODEX_CV_WORKSPACE = str(tmp_path)
    settings.CODEX_CV_ENABLED = True
    settings.CODEX_CV_OWNER_EMAIL = 'owner@example.test'
    (tmp_path/'CVs').mkdir(); (tmp_path/'output').mkdir()
    cache.clear(); cv_tasks._tasks.clear()
    owner = User.objects.create_user('owner', email='owner@example.test', password='pw')
    cv_assets(owner)
    state = SimpleNamespace(owner=owner, root=tmp_path, client=APIClient(), full=[], compiled=[])
    state.client.force_authenticate(owner)
    state.job = JobLead.objects.create(company='ACME', title='AI Engineer', raw_description='Python', created_by=owner, url='https://a.example/jobs/1',
                                       original_source_text='Python role with enough original posting text to generate from.')

    def add(folder, stem, key='', language='', job=None):
        tex = tmp_path/folder/f'{stem}.tex'
        tex.write_text(f'text of {stem}', encoding='utf-8'); tex.with_suffix('.pdf').write_bytes(b'%PDF-old')
        kind = 'letter' if key else 'cv'
        _record_artifact_metadata(job or state.job, owner.pk, {f'{kind}_tex': str(tex), f'{kind}_pdf': str(tex.with_suffix('.pdf'))}, key, language)
        return str(tex)
    state.add = add
    state.cv_de = add('CVs', 'Owner-CV-DE', language='de')
    state.letter = add('output', 'Owner-Anschreiben', 'anschreiben')
    state.other_letter = add('output', 'Owner-Bewerbung', 'bewerbungsschreiben')
    state.message = add('output', 'Owner-Message', 'anschreiben:short')
    state.cv_en = add('CVs', 'Owner-CV-EN', language='en')  # the newest, so the job's current CV
    monkeypatch.setattr('jobradar.views.validate_model_capability', lambda *args, **kwargs: None)
    monkeypatch.setattr('jobradar.views.load_candidate_evidence', lambda *args: 'profile')

    def full(job_id, user_id, profile, cv_key, letter_key, create_letter, *pick, **kwargs):
        state.full.append({'cv_key': cv_key, 'letter_key': letter_key, 'create_letter': create_letter, **kwargs})
        return f'full-{len(state.full)}'
    monkeypatch.setattr('jobradar.views.start_cv_task', full)

    def post(action, **body):
        return state.client.post(f'/api/jobs/{state.job.id}/cv-generation/{action}/', body, format='json')
    state.post = post
    return state


def _fake_pdflatex(monkeypatch):
    def run(command, cancelled=None, cwd=None, **kwargs):
        (Path(cwd)/Path(command[-1]).with_suffix('.pdf')).write_bytes(b'%PDF-new')
        return SimpleNamespace(returncode=0, stdout='', stderr='')
    monkeypatch.setattr(cv_generator, '_run_command', run)
    monkeypatch.setattr(cv_generator, '_pdf_pages', lambda pdf: 1)
    # In the calling thread: parallel task threads lock the shared in-memory test database.
    monkeypatch.setattr(cv_tasks, 'Thread', lambda target, args=(), kwargs=None, **_: SimpleNamespace(start=lambda: target(*args, **(kwargs or {}))))


def _finish(env, response):
    ids = [task['id'] for task in response.data.get('tasks', [])] or [response.data['task_id']]
    for task_id in ids:
        task = cv_tasks.get_cv_task(task_id, env.owner.id)
        assert task['status'] == 'ready', task['error']


def test_the_preview_lists_every_document_on_disk_with_its_letter_template(env):
    Path(env.other_letter).unlink()
    files = env.client.get(f'/api/jobs/{env.job.id}/cv-generation/').data['generated_files']
    assert {(Path(row['tex']).name, row['kind'], row['letter_template']) for row in files if not row['missing']} == {
        ('Owner-CV-EN.tex', 'cv', ''), ('Owner-CV-DE.tex', 'cv', ''), ('Owner-Anschreiben.tex', 'letter', 'anschreiben'),
        ('Owner-Message.tex', 'message', 'anschreiben')}


def test_a_second_cv_is_adjusted_alone_with_its_own_language(env):
    response = env.post('revise-latest', instructions='Make the profile shorter.', documents=[env.cv_de], cv_template='en', letter_template='anschreiben')
    assert response.status_code == 202 and 'tasks' not in response.data
    [run] = env.full
    assert (run['source_cv'], run['source_letter'], run['create_cv'], run['create_letter'], run['cv_key']) == (env.cv_de, None, True, False, 'de')


def test_one_cv_and_one_letter_stay_one_run(env):
    env.post('revise-latest', instructions='Make it shorter.', documents=[env.cv_en, env.other_letter], cv_template='en', letter_template='anschreiben')
    [run] = env.full
    assert (run['source_cv'], run['source_letter'], run['cv_key'], run['letter_key']) == (env.cv_en, env.other_letter, 'en', 'bewerbungsschreiben')


def test_several_documents_run_one_each_with_their_own_template(env):
    response = env.post('revise-latest', instructions='Make it shorter.', documents=[env.cv_de, env.cv_en, env.letter, env.message], cv_template='en', letter_template='bewerbungsschreiben')
    runs = {run['source_cv'] or run['source_letter']: run for run in env.full}
    assert set(runs) == {env.cv_de, env.cv_en, env.letter, env.message} and len(env.full) == 4
    assert runs[env.cv_de]['cv_key'] == 'de' and runs[env.cv_en]['cv_key'] == 'en'
    assert runs[env.letter]['letter_key'] == 'anschreiben' and 'generation_options' not in runs[env.letter]
    assert runs[env.message]['generation_options'] == {'short_message': True}
    assert all(run['auto_clipboard'] is False for run in env.full)
    assert sorted(task['documents'][0] for task in response.data['tasks']) == sorted(Path(path).name for path in runs)


@pytest.mark.parametrize('broken', ['cv_en', 'cv_de'])  # the first started, then the second
def test_a_document_that_cannot_start_is_named_and_the_others_keep_running(env, monkeypatch, broken):
    def start(*args, **kwargs):
        if kwargs['source_cv'] == getattr(env, broken):
            raise RuntimeError('restarting')
        return 'started'
    monkeypatch.setattr('jobradar.views.start_cv_task', start)
    response = env.post('revise-latest', instructions='Make it shorter.', documents=[env.cv_en, env.cv_de])
    assert response.status_code == 202 and response.data['task_id'] == 'started'
    assert {task['documents'][0]: task['id'] for task in response.data['tasks']} == {
        name: '' if Path(getattr(env, broken)).name == name else 'started' for name in ('Owner-CV-EN.tex', 'Owner-CV-DE.tex')}
    monkeypatch.setattr('jobradar.views.start_cv_task', lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError('restarting')))
    assert env.post('revise-latest', instructions='Make it shorter.', documents=[env.cv_en, env.cv_de]).status_code == 503


@pytest.mark.parametrize(('action', 'body'), [
    ('recompile-latest', {}),
    ('revise-latest', {'instructions': 'OLD:\ntext of Owner-CV-DE\nNEW:\nnew de\n\nOLD:\ntext of Owner-CV-EN\nNEW:\nnew en'}),
])
def test_parallel_tasks_leave_the_clipboard_to_the_copy_ticks(env, monkeypatch, action, body):
    _fake_pdflatex(monkeypatch)
    copied = []
    monkeypatch.setattr(cv_tasks, '_copy_to_clipboard', lambda text: copied.append(text) or True)
    _finish(env, env.post(action, documents=[env.cv_de, env.cv_en], **body))
    assert copied == []
    _finish(env, env.post('recompile-latest', documents=[env.cv_de]))
    assert len(copied) == 1  # one run still copies by itself, as before


def test_exact_edits_write_only_the_ticked_documents(env, monkeypatch):
    _fake_pdflatex(monkeypatch)
    before = {path: Path(path).read_bytes() for path in (env.cv_en, env.cv_de, env.letter, env.other_letter, env.message)}
    # Blocks for two ticked documents, sent once; the third ticked document has none and stays as it is.
    instructions = 'OLD:\ntext of Owner-CV-DE\nNEW:\nnew German text\n\nOLD:\ntext of Owner-Bewerbung\nNEW:\nnew letter text'
    response = env.post('revise-latest', instructions=instructions, documents=[env.cv_de, env.other_letter, env.letter])
    assert response.status_code == 202 and env.full == []
    _finish(env, response)
    assert Path(env.cv_de).read_text(encoding='utf-8') == 'new German text'
    assert Path(env.other_letter).read_text(encoding='utf-8') == 'new letter text'
    for path in (env.cv_en, env.letter, env.message):
        assert Path(path).read_bytes() == before[path] and Path(path).with_suffix('.pdf').read_bytes() == b'%PDF-old'


def test_no_letter_ticked_leaves_every_letter_alone(env, monkeypatch):
    _fake_pdflatex(monkeypatch)
    _finish(env, env.post('recompile-latest', documents=[env.cv_de, env.cv_en]))
    assert all(Path(path).with_suffix('.pdf').read_bytes() == b'%PDF-new' for path in (env.cv_de, env.cv_en))
    assert all(Path(path).with_suffix('.pdf').read_bytes() == b'%PDF-old' for path in (env.letter, env.other_letter, env.message))


def test_an_exact_block_only_in_the_unticked_current_document_is_still_applied(env, monkeypatch):
    # TASK-278 AC9, for a type with nothing ticked: two letters ticked, the block is in the current CV.
    _fake_pdflatex(monkeypatch)
    response = env.post('revise-latest', instructions='OLD:\ntext of Owner-CV-EN\nNEW:\nnew English text', documents=[env.letter, env.other_letter])
    assert response.status_code == 202 and env.full == []
    _finish(env, response)
    assert Path(env.cv_en).read_text(encoding='utf-8') == 'new English text' and Path(env.cv_de).read_text(encoding='utf-8') == 'text of Owner-CV-DE'


def test_copy_returns_exactly_the_ticked_documents(env):
    text = env.post('tex', documents=[env.cv_de, env.other_letter]).data['text']
    assert text.startswith('% Job listing: https://a.example/jobs/1\n\n')
    assert [line for line in text.splitlines() if line.startswith('% =====')] == ['% ===== Owner-CV-DE.tex =====', '% ===== Owner-Bewerbung.tex =====']
    assert 'text of Owner-CV-DE' in text and 'text of Owner-Bewerbung' in text and 'Owner-CV-EN' not in text and 'Owner-Anschreiben' not in text
    assert env.post('tex', documents=[env.cv_de]).data['text'] == '% Job listing: https://a.example/jobs/1\n\ntext of Owner-CV-DE'


@pytest.mark.parametrize('action', ['revise-latest', 'recompile-latest', 'tex'])
def test_only_the_jobs_own_documents_on_disk_are_accepted(env, action, tmp_path_factory):
    stranger = tmp_path_factory.mktemp('elsewhere')/'secret.tex'
    stranger.write_text('secret', encoding='utf-8')
    other_job = JobLead.objects.create(company='Other', title='Role', raw_description='Python', created_by=env.owner)
    foreign = env.add('CVs', 'Owner-CV-Other', language='de', job=other_job)
    Path(env.letter).unlink()
    for path in (str(stranger), foreign, env.letter, str(Path(env.root)/'CVs'/'..'/'CVs'/'missing.tex')):
        response = env.post(action, instructions='Make it shorter.', documents=[env.cv_en, path])
        assert response.status_code == 400 and 'secret' not in str(response.data), path
    for documents in ([], 'Owner-CV-EN.tex', [1]):
        assert env.post(action, instructions='Make it shorter.', documents=documents).status_code == 400
    assert env.full == [] and stranger.read_text(encoding='utf-8') == 'secret'
    outsider = APIClient(); outsider.force_authenticate(User.objects.create_user('outsider', email='outsider@example.test'))
    assert outsider.post(f'/api/jobs/{env.job.id}/cv-generation/{action}/', {'instructions': 'x', 'documents': [env.cv_en]}, format='json').status_code == 404


def test_preparation_files_are_selectable(env):
    prepared = env.root/'CVs'/'Owner-CV-Prepared.tex'
    prepared.write_text('prepared', encoding='utf-8')
    _edit_sidecar(env.job, env.owner.pk, lambda data: data.update(preparation={'variants': {'cv-de': {'document': 'cv', 'language': 'de', 'status': 'ready', 'files': {'cv_tex': str(prepared)}}}}))
    assert env.post('tex', documents=[str(prepared)]).data['text'].endswith('prepared')


def test_without_a_document_list_the_current_documents_are_used_as_before(env):
    env.post('revise-latest', instructions='Make it shorter.', create_letter=False, cv_template='en', letter_template='anschreiben')
    [run] = env.full
    assert (run['source_cv'], run['create_cv'], run['create_letter'], run['cv_key']) == (env.cv_en, True, False, 'en') and 'auto_clipboard' not in run
