"""TASK-334: every Adjust leaves one adjustments.jsonl line, and a failed compile leaves its .tex/.log,
so a failure can be solved after the task (in memory) and its temp dir are gone."""
import json
from pathlib import Path

import pytest

from jobradar.services import cv_generator
from jobradar.tests.test_literal_edits import env, owner  # noqa: F401 -- fixtures

EXACT = 'OLD:\nSenior Backend Engineer\\\\[2pt]\n\nNEW:\nStaff Backend Engineer\\\\[2pt]\n'


@pytest.fixture
def workspace(tmp_path, settings):
    path=tmp_path/'workspace'
    path.mkdir()
    settings.CODEX_CV_WORKSPACE=str(path)
    return path


def _entries(workspace):
    return [json.loads(line) for line in (workspace/'.dachapply-logs'/'adjustments.jsonl').read_text(encoding='utf-8').splitlines()]


def test_exact_adjust_logs_one_entry_with_route_and_instructions(env, workspace):
    task=env.revise(EXACT)
    assert task['status']=='ready', task
    [entry]=_entries(workspace)
    assert entry['route']=='exact' and entry['instructions']==EXACT.strip() and entry['status']=='ready'
    assert entry['job_id']==env.job.id and entry['company']=='ACME' and entry['documents']==['cv']
    assert entry['main_changes'][0]=='Applied exact OLD/NEW replacements without AI.' and entry['failed_files']==[]


def test_failed_compile_saves_tex_and_log_and_the_entry_lists_them(env, workspace, monkeypatch):
    env.compile_ok=False
    fake=cv_generator._run_command
    def pdflatex(command, cancelled=None, cwd=None, **kwargs):
        (Path(cwd)/Path(command[-1]).with_suffix('.log')).write_text('! Undefined control sequence.\nl.12 \\foo\n', encoding='utf-8')
        return fake(command, cancelled, cwd=cwd, **kwargs)
    monkeypatch.setattr(cv_generator, '_run_command', pdflatex)
    task=env.revise(EXACT)
    assert task['status']=='failed' and 'Undefined control sequence' in task['error']
    [entry]=_entries(workspace)
    saved=sorted(Path(path) for path in entry['failed_files'])
    assert [path.suffix for path in saved]==['.log','.tex'] and all(path.parent==workspace/'.dachapply-logs'/'failed' and path.is_file() for path in saved)
    assert saved[1].name.endswith('-Jane-CV.tex') and 'Staff Backend Engineer' in saved[1].read_text(encoding='utf-8')
    assert entry['status']=='failed' and 'Undefined control sequence' in entry['error'] and 'l.12' in entry['diagnostics_head']


def test_unwritable_log_location_never_breaks_the_task(env, workspace):
    (workspace/'.dachapply-logs').write_text('a file where the log directory should be', encoding='utf-8')
    assert env.revise(EXACT)['status']=='ready'
    env.source.write_bytes(env.original)
    env.compile_ok=False
    task=env.revise(EXACT)
    assert task['status']=='failed' and 'LaTeX could not compile' in task['error']
