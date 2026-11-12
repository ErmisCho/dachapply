"""TASK-370: hermetic fixture/runner contracts; no provider or network calls."""
import functools
import hashlib
import inspect
import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection

from jobradar.models import CvAsset, JobEvaluation, JobLead, UserProfile
from jobradar.services import benchmark as bench, application_prep as prep, cv_generator as gen, cv_tasks
from jobradar.tests.test_application_prep import POSTING, _req


@pytest.fixture
def exported(tmp_path, settings, monkeypatch, db):
    workspace = tmp_path / 'owner-workspace'
    workspace.mkdir()
    (workspace / 'secret-unrelated.txt').write_text('do not export')
    settings.CODEX_CV_WORKSPACE = str(workspace)
    settings.CODEX_CV_OWNER_EMAIL = 'owner@example.test'
    user = User.objects.create(username='owner', email=settings.CODEX_CV_OWNER_EMAIL, first_name='Example', last_name='Owner')
    UserProfile.whole.update_or_create(user=user, defaults={'candidate_profile': 'Python engineer', 'candidate_evidence': 'Python evidence', 'can_generate_cv': True})
    for key, kind in [('en', 'cv'), ('cover', 'letter'), ('alternative', 'letter')]:
        CvAsset.objects.create(user=user, kind=kind, key=key, language='en', label='Same label', filename=key+'.tex', source='template')
    for n in range(2):
        job = JobLead.objects.create(created_by=user, company='Same company', title='Same role', status='to_apply', original_source_text=POSTING,
                                    application_requirements=_req('en', cover_letter='required'))
        JobEvaluation.objects.create(job=job, fit_score=80, priority='high', recommendation='apply')
    monkeypatch.setattr(gen, 'available_model_options', lambda: pytest.fail('Export must not discover models'))
    output = tmp_path / 'fixture'
    statements = []
    def capture(execute, sql, params, many, context):
        statements.append(sql)
        return execute(sql, params, many, context)
    before = list(JobLead.objects.values())
    with connection.execute_wrapper(capture):
        assert bench.export_fixture(user.email, '2', output) == 2
    assert list(JobLead.objects.values()) == before
    assert not any(sql.lstrip().upper().startswith(('INSERT', 'UPDATE', 'DELETE')) for sql in statements)
    assert not (output / 'workspace' / 'secret-unrelated.txt').exists()
    return output, user


def test_export_is_read_only_and_private_inputs_only(exported):
    output, user = exported
    assert len(json.loads((output / 'jobs.json').read_text())) == 2
    profile = json.loads((output / 'profile.json').read_text())
    assert profile['profile']['candidate_evidence'] == 'Python evidence'
    assert len(profile['assets']) == 3
    assert (output / 'workspace' / 'application-rules.md').exists()
    assert not {'password', 'mailbox_calendar_ids', 'submit_for_id'} & profile['profile'].keys()


def test_export_refuses_repo_before_query_or_output(tmp_path, monkeypatch):
    target = Path(__file__).resolve().parents[3] / 'must-not-exist-benchmark'
    with pytest.raises(CommandError, match='outside'):
        call_command('benchmark_export', email='private@example.test', jobs='1', out=str(target))
    assert not target.exists()


def test_run_refuses_non_sqlite_before_reading_fixture(tmp_path, monkeypatch):
    monkeypatch.setattr(connection, 'vendor', 'postgresql')
    with pytest.raises(CommandError, match='sqlite'):
        call_command('benchmark_run', fixture='missing', experiment='concurrency', out=str(tmp_path/'out'))
    assert not (tmp_path/'out').exists()


def test_metrics_package_wait_and_errors():
    def row(kind, second, status='ready', recommended=False, **kwargs):
        return dict(document=kind, language='en', finished_at=datetime.fromtimestamp(100+second, timezone.utc).isoformat(), status=status, recommended=recommended, **kwargs)
    states = [{'variants': {'cv': row('cv', 3), 'letter': row('letter', 5, recommended=True), 'alt': row('letter', 9)}},
              {'variants': {'cv': row('cv', 8, 'cancelled'), 'letter': row('letter', 9, 'failed', retry_at='later')}}]
    result = bench.metrics(states, 100, 110)
    assert result['time_to_first_useful_package_seconds'] == 5
    assert result['total_seconds'] == 10 and result['documents_per_minute'] == 18
    assert {e['error_class'] for e in result['errors']} == {'cancellation', 'provider-limit'}
    states[0]['variants']['message'] = row('message', 7)
    assert bench.metrics(states, 100, 110)['time_to_first_useful_package_seconds'] == 7


def test_overwrite_checks_duplicate_changed_and_wrong_owner(tmp_path):
    path = tmp_path / 'cv.tex'
    path.write_text('original')
    recorder = bench.Recorder(tmp_path)
    row = dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest(), job_id=1, user_id=2)
    recorder.artifacts = [row]
    assert recorder.overwrite_check({1: 2})['ok']
    recorder.artifacts.append(row.copy())
    path.write_text('overwritten')
    reasons = {e['reason'] for e in recorder.overwrite_check({1: 3})['errors']}
    assert reasons == {'duplicate artifact path', 'artifact changed or missing', 'job/account/workspace mismatch'}


@pytest.mark.parametrize('error,expected', [(gen.GenerationCancelled(), 'cancellation'), (gen.RecoverableGenerationError('limit', usage_limit=True), 'provider-limit'), (RuntimeError('bad'), 'failure')])
def test_model_requests_record_failures_and_repairs(tmp_path, error, expected):
    def model(prompt, schema, provider, model, effort='default', speed='normal', **kwargs):
        raise error
    recorder = bench.Recorder(tmp_path)
    with pytest.raises(type(error)):
        recorder.model(model)('AUTOMATIC REPAIR ATTEMPT', {}, 'openai', 'test', workdir=tmp_path)
    request = recorder.requests[0]
    assert request['error_class'] == expected and request['repair']
    assert request['end'] >= request['start']


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize('workers,real_generator', [(1, False), (2, False), (2, True)])
def test_real_queue_runs_all_variants_with_requested_concurrency(exported, tmp_path, monkeypatch, settings, workers, real_generator):
    fixture, owner = exported
    # TASK-370: remove only rows this fixture created, leaving a fresh scratch database.
    JobLead.objects.filter(created_by=owner).delete()
    User.objects.filter(pk=owner.pk).delete()
    monkeypatch.setattr(prep, '_queue', [])
    monkeypatch.setattr(prep, '_running', 0)
    monkeypatch.setattr(prep, '_analysing', set())
    options = [{'provider': 'openai', 'key': gen.CV_DEFAULT_MODEL[1], 'efforts': ['high'], 'default_effort': 'high'}]
    monkeypatch.setattr(prep, 'available_model_options', lambda: options)
    monkeypatch.setattr(prep, 'validate_model_capability', lambda *a, **kw: None)
    monkeypatch.setattr(gen.shutil, 'which', lambda name: name if real_generator else None)
    monkeypatch.setattr(gen, 'validate_model_capability', lambda *a, **kw: {})
    settings.CODEX_CV_CACHE = False
    settings.CODEX_CV_OPEN_OUTPUT_FOLDER = False
    compile_active, compile_maximum = 0, 0
    compile_dirs = set()
    def compile_command(command, cancelled=None, **kwargs):
        from types import SimpleNamespace
        nonlocal compile_active, compile_maximum
        if command[0] == 'pdflatex':
            with lock:
                compile_active += 1
                compile_maximum = max(compile_maximum, compile_active)
                compile_dirs.add(str(kwargs['cwd']))
            try:
                time.sleep(.01)
                (Path(kwargs['cwd']) / Path(command[-1]).with_suffix('.pdf')).write_bytes(b'%PDF-fake')
            finally:
                with lock:
                    compile_active -= 1
        return SimpleNamespace(returncode=0, stdout='', stderr='')
    monkeypatch.setattr(gen, '_run_command', compile_command)
    monkeypatch.setattr(gen, '_pdf_pages', lambda path: 1)
    def model(prompt, schema, provider, model, effort='default', speed='normal', **kwargs):
        if real_generator:
            if pair:
                pair.wait(timeout=10)
            return {'cv_tex': r'\documentclass{article}\begin{document}CV\end{document}',
                    'letter_tex': r'\documentclass{article}\begin{document}Letter\end{document}',
                    'changed_files': [], 'main_changes': [], 'unsupported_requirements_not_claimed': [], 'confirmations': {}}
        return {}
    monkeypatch.setattr(gen, 'run_structured_model', model)
    monkeypatch.setattr(prep, 'run_structured_model', model)
    monkeypatch.setattr(bench.job_evaluator, 'run_structured_model', model)
    lock = threading.Lock()
    active, maximum = 0, 0
    pair = threading.Barrier(2) if workers == 2 else None
    signature = inspect.signature(gen.generate_cv_package)
    @functools.wraps(gen.generate_cv_package)
    def generate(*args, **kwargs):
        nonlocal active, maximum
        bound = signature.bind(*args, **kwargs)
        bound.apply_defaults()
        values = bound.arguments
        with lock:
            active += 1
            maximum = max(maximum, active)
        try:
            if pair:
                pair.wait(timeout=10)
            gen.run_structured_model('fixture prompt', {}, values['provider'], values['model'], values['effort'], values['speed'], workdir=settings.CODEX_CV_WORKSPACE)
            time.sleep(.03)
            kind = 'cv' if values['create_cv'] else 'letter'
            path = Path(settings.CODEX_CV_WORKSPACE) / f"{values['user_id']}-{values['job'].pk}-{kind}-{values['letter_key']}-{values['name_suffix']}.tex"
            path.write_text('fake document')
            return b'zip', 'fake.zip', {kind+'_tex': str(path)}
        finally:
            with lock:
                active -= 1
    if not real_generator:
        monkeypatch.setattr(cv_tasks, 'generate_cv_package', generate)
    old_workspace, old_workers = settings.CODEX_CV_WORKSPACE, settings.PREP_QUEUE_CONCURRENCY
    result = bench.run_fixture(fixture, 'concurrency', None, workers, tmp_path/'results')
    if real_generator:
        assert compile_maximum == 1 and len(compile_dirs) == 6  # actual shared TeX lock, separate temporary compile dirs
    else:
        assert maximum == workers
    assert result['overwrite_check']['ok'], result['overwrite_check']
    assert result['metrics']['ready_documents'] == 6
    assert result['metrics']['errors'] == []
    assert len(result['requests']) == 6
    assert len({a['path'] for a in result['artifacts']}) == (12 if real_generator else 6)
    assert settings.CODEX_CV_WORKSPACE == old_workspace and settings.PREP_QUEUE_CONCURRENCY == old_workers
    assert result['workspace'] != old_workspace
    assert (tmp_path/'results'/'summary.md').exists()
    assert not list((fixture/'workspace').glob('*.tex'))
    # TASK-370: clean up only the retained temporary workspace made by this run.
    import shutil
    shutil.rmtree(result['workspace'])
