"""TASK-303: CV/prep default model, estimates learned from cv-benchmarks.jsonl, and the CV-only
readjustment that failed before any model call."""
import json
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from django.contrib.auth.models import User

from jobradar.models import JobLead
from jobradar.services import cv_tasks
from jobradar.services.cv_generator import cv_default_choice, generate_cv_package


def _option(key, efforts, provider='openai'):
    return {'provider': provider, 'key': key, 'label': key, 'efforts': efforts, 'default_effort': 'medium', 'fast_tier': 'priority'}


def test_cv_default_is_gpt_6_1_sol_at_high_else_newest_at_highest_effort_not_above_high():
    sol = _option('gpt-6.1-sol', ['low', 'medium', 'high', 'xhigh'])
    newest = _option('gpt-6.2', ['low', 'medium', 'xhigh'])
    assert cv_default_choice([newest, sol]) == (sol, 'high')
    assert cv_default_choice([_option('sonnet', ['low', 'max'], 'anthropic'), newest]) == (newest, 'medium')
    assert cv_default_choice([_option('qwen', ['default'], 'ollama')]) == (None, '')


def _row(model, effort, generating, *, cv=True, letter=False, route='generation', status='ready', speed='fast', cache_hit=False):
    stages = {'preparing': .1, 'generating': generating, 'generated': 0.0, 'saving': .2}
    stages.update({'compiling_cv': 1.5, 'cv_compiled': 0.0} if cv else {})
    stages.update({'compiling_letter': 1.3, 'letter_compiled': 0.0} if letter else {})
    return {'route': route, 'provider': 'openai', 'model': model, 'effort': effort, 'speed': speed, 'create_cv': cv, 'create_letter': letter,
            'status': status, 'cache_hit': cache_hit, 'stage_seconds': stages}


@pytest.fixture
def history(settings, tmp_path):
    settings.CODEX_CV_WORKSPACE = str(tmp_path)
    path = tmp_path/'.dachapply-cache'/'cv-benchmarks.jsonl'
    path.parent.mkdir()

    def write(*rows):
        path.write_text(''.join(json.dumps(row)+'\n' for row in rows), encoding='utf-8')
    return write


def test_estimate_is_the_median_of_recent_successful_runs_of_the_exact_group(history):
    history(*[_row('gpt-6.1-sol', 'xhigh', 900) for _ in range(5)],  # older than the 10 most recent
            *[_row('gpt-6.1-sol', 'xhigh', seconds) for seconds in (340, 350, 355, 360, 370, 345, 352, 358, 365, 357)],
            _row('gpt-6.1-sol', 'xhigh', 5000, status='failed'), _row('gpt-6.1-sol', 'xhigh', 5000, cache_hit=True),
            _row('gpt-6.1-sol', 'xhigh', 200, cv=False, letter=True), _row('gpt-5.6-sol', 'xhigh', 120))
    plan, defaults, _ = cv_tasks._task_timing('openai', 'gpt-6.1-sol', 'xhigh', 'fast', True, False, False)
    assert defaults['generating'] == 356 and defaults['compiling_cv'] == 1.5
    assert cv_tasks.estimate_seconds('openai', 'gpt-6.1-sol', 'xhigh', 'fast', True, False) == {'seconds': 360, 'history': 'measured'}
    # Each document mix is its own group: the letter-only run does not move the CV estimate, and back.
    assert cv_tasks._task_timing('openai', 'gpt-6.1-sol', 'xhigh', 'fast', False, True, False)[1]['generating'] == 200
    assert cv_tasks._task_timing('openai', 'gpt-5.6-sol', 'xhigh', 'fast', True, False, False)[1]['generating'] == 120


def test_without_its_own_effort_the_same_model_is_scaled_and_never_another_model_borrowed(history):
    history(_row('gpt-6.1-sol', 'xhigh', 320), _row('gpt-5.6-sol', 'high', 100))
    other = cv_tasks.estimate_seconds('openai', 'gpt-6.1-sol', 'high', 'fast', True, False)
    assert other['history'] == 'other_effort'
    assert cv_tasks._task_timing('openai', 'gpt-6.1-sol', 'high', 'fast', True, False, False)[1]['generating'] == pytest.approx(320*1.3/1.6)
    # gpt-6.1-sol at normal speed, a revision, and an unseen model have no runs: said so, and padded.
    for args in (('gpt-6.1-sol', 'high', 'normal', True, False, False), ('gpt-6.1-sol', 'high', 'fast', True, False, True), ('gpt-7', 'high', 'fast', True, False, False)):
        assert cv_tasks._learned_timing(('openai', *args))[1] == 'none'
    assert cv_tasks._task_timing('openai', 'gpt-7', 'medium', 'normal', True, False, False)[1]['generating'] == 88*cv_tasks.NO_HISTORY_FACTOR


def test_live_task_counts_down_from_the_learned_estimate_and_says_when_there_is_none(history, job, monkeypatch):
    history(*[_row('gpt-6.1-sol', 'high', 200) for _ in range(3)])
    release = __import__('threading').Event()

    def generate(job, profile, cv, letter, create_letter, provider, model, effort, speed, progress, *args, **kwargs):
        progress(5, 'Preparing templates'); progress(10, 'Generating CV')
        release.wait(2)
        return b'zip', 'application.zip', {}
    monkeypatch.setattr(cv_tasks.JobLead.objects, 'get', lambda id: job)
    monkeypatch.setattr(cv_tasks, 'generate_cv_package', generate)
    monkeypatch.setattr(cv_tasks, '_copy_to_clipboard', lambda text: True)
    measured = cv_tasks.start_cv_task(job.id, job.created_by_id, 'p', 'en', '', False, 'openai', 'gpt-6.1-sol', 'high', 'fast')
    unseen = cv_tasks.start_cv_task(job.id, job.created_by_id, 'p', 'en', '', False, 'openai', 'gpt-7', 'high', 'fast')
    try:
        for _ in range(100):
            task = cv_tasks.get_cv_task(measured, job.created_by_id)
            if task['status'] == 'running' and task['step_label'] == 'Generating documents':
                break
            time.sleep(.01)
        assert task['estimate_history'] == 'measured' and 195 <= task['estimated_seconds_remaining'] <= 205
        assert cv_tasks.get_cv_task(unseen, job.created_by_id)['estimate_history'] == 'none'
    finally:
        release.set()
        # Let both workers finish while the test database still exists.
        for _ in range(200):
            if all(cv_tasks.get_cv_task(task_id, job.created_by_id)['status'] in ('ready', 'failed') for task_id in (measured, unseen)):
                break
            time.sleep(.01)


def test_a_failed_runs_reason_is_kept_in_its_benchmark_row():
    task = {'id': 't', 'status': 'failed', 'error': 'Current generated motivation letter PDF is unavailable.', '_created_at': time.monotonic(),
            '_estimate_key': ('openai', 'gpt-6.1-sol', 'medium', 'fast', True, False, True)}
    assert cv_tasks._benchmark_row(task, time.monotonic())['error'] == 'Current generated motivation letter PDF is unavailable.'
    assert 'error' not in cv_tasks._benchmark_row({**task, 'status': 'ready'}, time.monotonic())


def test_with_expected_seconds_covers_every_effort_and_offered_speed(history):
    history(_row('gpt-6.1-sol', 'high', 200, letter=True))
    [option] = cv_tasks.with_expected_seconds([{**_option('gpt-6.1-sol', ['medium', 'high']), 'fast_tier': ''}])
    assert set(option['expected_seconds']['generation']['both']) == {'medium|normal', 'high|normal'}
    assert option['expected_seconds']['revision']['cv']['high|normal']['history'] == 'none'


@pytest.fixture
def job(db):
    owner = User.objects.create_user('timing-owner')
    return JobLead.objects.create(company='Acme', title='Engineer', raw_description='Python', created_by=owner)


def test_cv_only_layout_readjustment_ignores_a_letter_whose_pdf_is_elsewhere(db, tmp_path, monkeypatch, settings, cv_assets):
    # TASK-303 AC4, the 2026-10-15 GPT-6.1 failures: a CV-only readjustment handed the job's letter to
    # the layout check, whose PDF the owner had renamed in Explorer, and failed in 0.5 s before any
    # model call -- so no validation reason (#271) was ever produced.
    (tmp_path/'CVs').mkdir(); (tmp_path/'output').mkdir()
    settings.CODEX_CV_WORKSPACE = str(tmp_path); settings.CODEX_CV_OPEN_OUTPUT_FOLDER = False; settings.CODEX_CV_CACHE = False
    monkeypatch.setattr('jobradar.services.cv_generator.shutil.which', lambda command: command)
    monkeypatch.setattr('jobradar.services.cv_generator.available_model_options', lambda: [_option('gpt-6.1-sol', ['medium', 'high'])])
    user = User.objects.create_user('layout-owner')
    cv_assets(user)
    job = JobLead.objects.create(company='Wienerberger AG', title='AI Solutions Engineer', raw_description='Wir suchen eine Person mit Erfahrung und Kenntnissen für diese Aufgaben.', created_by=user)
    confirmations = dict.fromkeys(['cv_max_2_pages', 'letter_max_1_page', 'no_orphaned_employer_headings', 'no_text_overlap', 'nothing_after_end_document', 'links_work', 'photo_loads_if_used', 'no_invented_tools_or_overclaims'], True)
    cv_tex = tmp_path/'CVs'/'cv.tex'
    cv_tex.write_text('\\documentclass{article}\\begin{document}Old\\end{document}', encoding='utf-8'); cv_tex.with_suffix('.pdf').write_bytes(b'pdf')
    letter_tex = tmp_path/'output'/'letter.tex'
    letter_tex.write_text('\\documentclass{article}\\begin{document}Letter\\end{document}', encoding='utf-8')  # its PDF was renamed away
    inspected = []

    def fake_run(command, **kwargs):
        if command[0] in ('pdfinfo', 'pdftoppm'):
            inspected.append(Path(command[-2 if command[0] == 'pdftoppm' else -1]).name)
            return SimpleNamespace(returncode=0, stdout='Pages: 1', stderr='')
        if command[0] == 'codex':
            Path(command[command.index('--output-last-message')+1]).write_text(json.dumps({
                'cv_tex': '\\documentclass{article}\\begin{document}New\\end{document}', 'changed_files': [], 'main_changes': [],
                'unsupported_requirements_not_claimed': [], 'confirmations': confirmations}))
            return SimpleNamespace(returncode=0, stdout='ok', stderr='')
        (Path(kwargs['cwd'])/Path(command[-1]).with_suffix('.pdf')).write_bytes(b'pdf')
        return SimpleNamespace(returncode=0, stdout='ok', stderr='')
    monkeypatch.setattr('jobradar.services.cv_generator.subprocess.run', fake_run)

    _, _, saved = generate_cv_package(job, 'profile', 'de', '', False, 'openai', 'gpt-6.1-sol', 'medium', speed='fast', create_cv=True,
                                      source_cv=str(cv_tex), source_letter=str(letter_tex), revision_instructions='Tighten the spacing', user_id=user.id)
    assert 'New' in Path(saved['cv_tex']).read_text(encoding='utf-8')
    assert 'letter.pdf' not in inspected and 'cv.pdf' in inspected


def test_generation_preview_offers_the_cv_default_and_per_setting_durations(db, history, settings, monkeypatch):
    from rest_framework.test import APIClient
    settings.CODEX_CV_OWNER_EMAIL = 'owner@example.test'
    owner = User.objects.create_user('preview-owner', email='owner@example.test')
    job = JobLead.objects.create(company='Acme', title='Engineer', raw_description='Python', created_by=owner)
    monkeypatch.setattr('jobradar.services.cv_generator.available_model_options', lambda: [_option('gpt-6.2', ['high']), _option('gpt-6.1-sol', ['medium', 'high', 'xhigh'])])
    history(_row('gpt-6.1-sol', 'high', 300))
    client = APIClient(); client.force_authenticate(owner)
    preview = client.get(f'/api/jobs/{job.id}/cv-generation/').data
    assert preview['default_pick'] == {'provider': 'openai', 'model': 'gpt-6.1-sol', 'effort': 'high'}
    sol = next(option for option in preview['models'] if option['key'] == 'gpt-6.1-sol')
    assert sol['expected_seconds']['generation']['cv']['high|fast']['history'] == 'measured'
