"""TASK-406.1/406.2: every failed document leaves private evidence and is grouped by its cause."""
import json
import os
import time
from pathlib import Path
from threading import Event
from types import SimpleNamespace

import pytest
from django.contrib.auth.models import User

from jobradar.models import JobLead
from jobradar.services import cv_generator, cv_tasks, error_occurrences, error_triage, failure_evidence
from jobradar.services.cv_generator import GenerationFailed, RecoverableGenerationError

INVALID = 'The selected model returned invalid application documents. Two automatic repair attempts also failed.'
BARE = ("Attempt 1: The selected model returned invalid application documents.\nletter_tex (2085 chars) is missing \\documentclass, \\begin{document}, \\end{document}; "
        "it starts with 'Sehr geehrter Herr Muster,\\n\\nan der'")


@pytest.fixture
def env(db, settings, tmp_path, monkeypatch):
    workspace, private = tmp_path/'workspace', tmp_path/'private'
    workspace.mkdir(); private.mkdir()
    settings.CODEX_CV_WORKSPACE = str(workspace)
    settings.ERROR_OCCURRENCE_LOCAL_DB = str(private/'occurrences.sqlite3')
    settings.DEBUG = True
    cv_tasks._tasks.clear()
    owner = User.objects.create_user('owner', email='owner@example.test', password='pw')
    job = JobLead.objects.create(company='Muster GmbH', title='Engineer', raw_description='Python', created_by=owner)

    def task(task_id='a'*32, **extra):
        now = time.monotonic()
        cv_tasks._tasks[task_id] = {
            'id': task_id, 'user_id': owner.pk, 'job_id': job.pk, 'status': 'running', 'progress': 5, 'stage': 'Working', 'error': '', 'artifacts': {}, 'report': None,
            'diagnostics': '', 'repair_attempts': 0, '_cancel': Event(), '_created_at': now, '_started_at': now, '_finished_at': None, '_stage_key': 'working', '_stage_started_at': now,
            '_stage_plan': [], '_stage_defaults': {}, '_estimate_key': ('x',), '_stage_times': {}, '_adjust': None, 'updated_at': time.time(),
            '_config': {'provider': 'openai', 'model': 'gpt', 'effort': 'low'}, **extra}
        return task_id
    return SimpleNamespace(workspace=workspace, owner=owner, job=job, task=task)


def test_a_failed_task_leaves_one_record_with_its_files(env):
    task_id = env.task(_failed_files=['x.tex', 'x.log'], _adjust={'route': 'exact', 'instructions': 'OLD: a'})
    cv_tasks._update(task_id, status='failed', error=INVALID, diagnostics=BARE)
    cv_tasks._update(task_id, status='failed', error=INVALID, diagnostics=BARE)  # a second report of the same end
    [row] = failure_evidence.records(env.owner.pk)
    assert (row['id'], row['job_id'], row['route'], row['model'], row['error'], row['files'], row['class']) == (task_id, env.job.pk, 'exact', 'gpt', INVALID, ['x.tex', 'x.log'], 'actionable')
    assert row['diagnostics'] == BARE and row['cause'] == 'Invalid document: the document (N chars) is missing \\documentclass, \\begin{document}, \\end{document}'
    assert failure_evidence.records(env.owner.pk + 1) == []


@pytest.mark.parametrize('status', ['ready', 'cancelled', 'scheduled'])
def test_only_a_final_failure_is_recorded(env, status):
    cv_tasks._update(env.task(), status=status, error='Usage limit reached')
    assert failure_evidence.records(env.owner.pk) == []


def test_a_scheduled_retry_that_then_fails_is_recorded(env):
    task_id = env.task()
    cv_tasks._update(task_id, status='scheduled', error='Usage limit reached')
    cv_tasks._update(task_id, status='running')
    cv_tasks._update(task_id, status='failed', error='Usage limit reached; try again later.')
    assert [row['class'] for row in failure_evidence.records(env.owner.pk)] == ['quota']


def test_saving_never_changes_the_task_result(env, monkeypatch):
    monkeypatch.setattr(failure_evidence, 'logs_dir', lambda: (_ for _ in ()).throw(OSError('disk full')))
    task_id = env.task()
    cv_tasks._update(task_id, status='failed', error=INVALID)
    assert cv_tasks._tasks[task_id]['status'] == 'failed' and failure_evidence.save_answer('a.tex', 'x') == []


def test_records_and_files_older_than_30_days_are_deleted(env):
    folder = env.workspace/'.dachapply-logs'
    (folder/'failures').mkdir(parents=True); (folder/'failed').mkdir()
    old, new, log = folder/'failures'/'old.json', folder/'failed'/'new.tex', folder/'adjustments.jsonl'
    stale = folder/'failed'/'old.tex'
    for path in (old, new, log, stale):
        path.write_text('{}', encoding='utf-8')
    for path in (old, stale, log):
        os.utime(path, (time.time() - 31*86400,)*2)
    cv_tasks._update(env.task(), status='failed', error=INVALID)
    assert not old.exists() and not stale.exists() and new.exists() and log.exists()


@pytest.mark.parametrize('answer', [
    'Sehr geehrter Herr Muster, nur der Text',  # job 2095, 2026-11-23: a bare letter body
    '\\documentclass{article}\\begin{document}\nOLD: leaked\n\\end{document}',  # TASK-404's guard
])
def test_every_rejected_model_answer_is_kept(env, monkeypatch, settings, cv_assets, answer):
    settings.CODEX_CV_CACHE = False
    (env.workspace/'CVs').mkdir(); (env.workspace/'output').mkdir()
    letter = env.workspace/'output'/'Letter.tex'
    letter.write_text('\\documentclass{article}\\begin{document}Text\\end{document}', encoding='utf-8')
    letter.with_suffix('.pdf').write_bytes(b'%PDF')
    cv_assets(env.owner)
    env.job.original_source_text = 'Python role with enough original posting text to generate from.'; env.job.save()
    monkeypatch.setattr(cv_generator, 'validate_model_capability', lambda *a, **k: None)
    monkeypatch.setattr(cv_generator.shutil, 'which', lambda name: name)
    monkeypatch.setattr(cv_generator, 'run_structured_model', lambda *a, **k: {
        'cv_tex': '', 'letter_tex': answer, 'changed_files': [], 'main_changes': [], 'unsupported_requirements_not_claimed': [], 'confirmations': {}})
    with pytest.raises(GenerationFailed) as failed:
        cv_generator.generate_cv_package(env.job, 'profile', 'de', 'anschreiben', True, 'openai', 'gpt', 'low', source_letter=str(letter), revision_instructions='Shorter.', create_cv=False, user_id=env.owner.pk)
    assert len(failed.value.saved_files) == 3  # one per attempt, names never collide
    assert {Path(path).read_text(encoding='utf-8') for path in failed.value.saved_files} == {answer}


def test_a_page_limit_failure_keeps_its_tex(env, monkeypatch, tmp_path):
    (tmp_path/'Letter.tex').write_text('long', encoding='utf-8')
    monkeypatch.setattr(cv_generator.shutil, 'which', lambda name: name)
    monkeypatch.setattr(cv_generator, '_run_command', lambda *a, **k: SimpleNamespace(returncode=0, stdout='', stderr=''))
    monkeypatch.setattr(cv_generator, '_pdf_pages', lambda pdf: 2)
    with pytest.raises(RecoverableGenerationError) as failed:
        cv_generator._compile_pdf(tmp_path, 'Letter.tex', False)
    assert [Path(path).suffix for path in failed.value.saved_files] == ['.tex']


# The errors really seen between 2026-10-21 and 2026-11-23.
def unicode_error(what, char, line):
    return f'LaTeX could not compile the {what}: LaTeX Error: Unicode character {char[0]} ({char[1]}) (line {line}).'


SAME = [
    (unicode_error('CV', ('≤', 'U+2264'), 205), unicode_error('motivation letter', ('→', 'U+2192'), 7)),
    ('LaTeX could not compile the motivation letter: LaTeX Error: Missing \\begin{document} (line 4).', 'LaTeX could not compile the CV: LaTeX Error: Missing \\begin{document} (line 91).'),
    ('The motivation letter exceeds its 1-page limit.', 'The CV exceeds its 2-page limit.'),
    ('Usage limit reached; resets at 19:27.', 'Usage limit reached; resets at 07:05.'),
]
DIFFERENT = ['LaTeX could not compile the CV: LaTeX Error: Lonely \\item--perhaps a missing list environment (line 12).',
             'LaTeX could not compile the CV: LaTeX Error: \\begin{itemize} on input line 115 ended by \\end{samepage} (line 9).',
             '[WinError 32] The process cannot access the file because it is being used by another process: \'C:\\\\ws\\\\a.pdf\'',
             'consuming input failed: server closed the connection unexpectedly', INVALID]


def test_the_same_cause_is_one_group_and_different_causes_are_not():
    for first, second in SAME:
        assert failure_evidence.signature(first) == failure_evidence.signature(second), failure_evidence.cause(first)
    everything = [first for first, _ in SAME] + DIFFERENT
    assert len({failure_evidence.signature(error) for error in everything}) == len(everything)
    other = BARE.replace('2085', '1773').replace('Herr Muster', 'Frau Beispiel').replace('letter_tex', 'cv_tex')
    assert failure_evidence.signature(INVALID, BARE) == failure_evidence.signature(INVALID, other) != failure_evidence.signature(INVALID)


def test_only_a_fault_of_the_platform_is_classed_as_a_bug():
    assert [failure_evidence.classify(pair[0]) for pair in SAME] == ['actionable', 'actionable', 'unknown', 'quota']
    assert [failure_evidence.classify(error) for error in DIFFERENT] == ['actionable', 'actionable', 'transient', 'transient', 'actionable']
    assert failure_evidence.classify('Something new') == failure_evidence.classify('') == 'unknown'


def test_a_group_files_one_bug_without_private_text(env, monkeypatch):
    calls, tasks = [], []

    def cli(args, **kwargs):
        calls.append((args[1:], str(kwargs['cwd'])))
        if args[2] == 'create':
            tasks.append({'id': f'TASK-{len(tasks) + 900}', 'title': args[3]})
        listed = [task for task in tasks if args[2] != 'list' or args[4] in task['title']]
        return SimpleNamespace(stdout=json.dumps({'tasks': listed}))
    monkeypatch.setattr(error_triage.subprocess, 'run', cli)
    for index in range(2):  # the same cause twice, with different private text
        cv_tasks._update(env.task(f'{index}'*32), status='failed', error=INVALID, diagnostics=BARE.replace('Muster', f'Geheim{index}'))
    cv_tasks._update(env.task('b'*32), status='failed', error='Usage limit reached; resets at 19:27.')
    cv_tasks._update(env.task('c'*32), status='failed', error='LaTeX could not compile the CV: LaTeX Error: Lonely \\item (line 3).')
    signature = failure_evidence.signature(INVALID, BARE)
    [proposal] = error_triage.triage(operation=signature, root=env.workspace)
    assert (proposal['action'], proposal['count'], proposal['task_id']) == ('create', 2, 'TASK-900')
    assert {cwd for _, cwd in calls} == {str(env.workspace)} and len(tasks) == 1
    shared = json.dumps([args for args, _ in calls])
    for private in ('Geheim', 'Muster', 'Sehr geehrter', 'documentclass', 'ACME'):
        assert private not in shared
    assert error_triage.triage(operation=signature, root=env.workspace) == []  # unchanged: no second task
    cv_tasks._update(env.task('d'*32), status='failed', error=INVALID, diagnostics=BARE)
    [again] = error_triage.triage(operation=signature, root=env.workspace)
    assert (again['action'], again['task_id'], len(tasks)) == ('update', 'TASK-900', 1)
    quota = error_triage.triage(operation=failure_evidence.signature('Usage limit reached; resets at 19:27.'), root=env.workspace)
    assert [(row['action'], row['task_id']) for row in quota] == [('classify', None)] and len(tasks) == 1


def test_collection_is_off_in_tests_and_never_blocks_the_record(env, settings):
    from config import settings_test
    assert settings_test.ERROR_OCCURRENCE_LOCAL_DB == ''
    settings.ERROR_OCCURRENCE_LOCAL_DB = ''
    cv_tasks._update(env.task(), status='failed', error=INVALID)
    assert error_occurrences.health() == 'disabled' and len(failure_evidence.records(env.owner.pk)) == 1
