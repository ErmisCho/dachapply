"""TASK-357: an automatic analysis (the pipeline's fit analysis, the requirements analysis) is given up once it ran
ANALYSIS_TIME_LIMIT -- its model process tree killed, or, for a block inside this process, its thread abandoned -- and
ends failed with Retry, so one hung run no longer holds _pipeline_lock and every analysis queued behind it. Model
discovery, where the live run hung (py-spy: `ollama list`'s pipes held by the server it started), no longer waits on
a pipe a grandchild holds.

The limit is patched to a fraction of a second. These run the analysis in a real worker thread, so the database is
committed (transaction=True), and each hang is bounded (HANG) so a missing limit fails a test instead of hanging it.
"""
import os
import signal
import subprocess
import sys
import threading
import time

import pytest

from jobradar.models import JobEvaluation, JobLead
from jobradar.services import application_prep, cv_generator, job_evaluator
from jobradar.tests.test_application_prep import POSTING, client, generator, owner, workspace  # noqa: F401 -- fixtures
from jobradar.tests.test_application_prep_queue import _items, tasks  # noqa: F401 -- fixtures
from jobradar.tests.test_job_evaluator import OLLAMA_OPTION, evaluation_for
from jobradar.tests.test_link_only_prep import LINK, _blocked, fetch  # noqa: F401 -- fixtures

HANG = 20  # seconds a "never returning" call lasts at most; every assertion below wants far less
LIMIT = 0.3
FIT_TIMED_OUT = 'Analysis failed: Stopped after 5 minutes, the time limit for one analysis. Press Retry.'
REQUIREMENTS_TIMED_OUT = 'Requirements analysis failed: Stopped after 5 minutes, the time limit for one analysis. Press Prepare to retry.'
OPTIONS = [{'provider': 'openai', 'key': 'gpt-6.1', 'efforts': ['medium'], 'default_effort': 'medium'}]


@pytest.fixture
def real_threads(monkeypatch, tasks):  # noqa: F811 -- after the generator's SyncThread, which runs work inline
    monkeypatch.setattr(application_prep, 'MINUTE', LIMIT / 5)  # TASK-360: the default 5 minutes last LIMIT seconds
    monkeypatch.setattr(application_prep, 'Thread', threading.Thread)
    monkeypatch.setattr(application_prep, '_piping', set())
    monkeypatch.setattr(job_evaluator, 'validate_model_capability', lambda *a, **k: OLLAMA_OPTION)
    release = threading.Event()
    yield release
    release.set()  # let an abandoned worker end now, then wait for it, so it never outlives the test's database
    for worker in [thread for thread in threading.enumerate() if thread.name == 'dachapply-analysis']:
        worker.join(HANG)


@pytest.fixture
def sleeper(monkeypatch):
    """The provider CLI the real run_structured_model builds becomes a Python process sleeping HANG seconds, run by
    the real _run_command and _stop_process. Returns the processes started, the model's first."""
    started = []

    class Recorded(subprocess.Popen):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            started.append(self)
    monkeypatch.setattr(cv_generator.subprocess, 'Popen', Recorded)
    monkeypatch.setattr(cv_generator.shutil, 'which', lambda name: 'model-cli')
    real = cv_generator._run_command
    monkeypatch.setattr(cv_generator, '_run_command', lambda command, *args, **kwargs:
                        real([sys.executable, '-c', f'import time; time.sleep({HANG})'], *args, **kwargs))
    return started


def _link_job(owner, title='Python Engineer'):  # noqa: F811
    return JobLead.objects.create(company='ACME', title=title, created_by=owner, url=LINK, original_source_text=POSTING)


@pytest.mark.django_db(transaction=True)
def test_an_in_process_block_fails_with_retry_and_the_next_analysis_runs(owner, client, fetch, real_threads, sleeper, monkeypatch):  # noqa: F811
    """The measured case: no model process at all, the run blocked inside this process (here: model discovery).
    Once released, the abandoned run writes nothing: the real run_structured_model refuses to start the model."""
    first, second = _link_job(owner), _link_job(owner, 'Backend Engineer')
    calls = []

    def discover():
        calls.append(1)
        if len(calls) == 1:
            real_threads.wait(HANG)
        return OPTIONS
    monkeypatch.setattr(application_prep, 'available_model_options', discover)
    began = time.monotonic()
    assert application_prep._pipeline(first.id, owner.pk) is False
    assert time.monotonic() - began < 5 and application_prep._in_lane == 0
    # The second job's analysis then runs to the end (its model answers at once).
    monkeypatch.setattr(job_evaluator, 'run_structured_model', lambda *a, **k: {'evaluations': [evaluation_for(second, recommendation='skip', fit_score=44)]})
    assert application_prep._pipeline(second.id, owner.pk) is True
    assert JobEvaluation.objects.filter(job=second).exists() and application_prep._state(second, owner)['pipeline']['stage'] == 'skipped'
    prep = application_prep._state(first, owner)
    assert prep['pipeline']['stage'] == 'failed' and prep['retry_at'] is None  # not transient: Retry is the owner's call
    assert [item for item in _items(client) if item['job_id'] == first.id] == [_blocked(first, FIT_TIMED_OUT)]
    # The late finish: discovery returns, and nothing is run, committed or recorded over the failure.
    monkeypatch.setattr(job_evaluator, 'run_structured_model', cv_generator.run_structured_model)
    real_threads.set()
    for worker in [thread for thread in threading.enumerate() if thread.name == 'dachapply-analysis']:
        worker.join(5)
    assert len(calls) == 2 and sleeper == []
    assert not JobEvaluation.objects.filter(job=first).exists() and application_prep._state(first, owner) == prep


@pytest.mark.django_db(transaction=True)
def test_the_fit_analysis_kills_a_model_process_that_outlives_the_limit(owner, client, fetch, real_threads, sleeper, monkeypatch):  # noqa: F811
    monkeypatch.setattr(application_prep, 'available_model_options', lambda: OPTIONS)
    model_started = lambda: [process for process in sleeper if process.args[0] == sys.executable]  # noqa: E731

    class LimitFromModelStart(threading.Thread):
        """Under full-suite load the work before the model call outlasted LIMIT, so the limit ran out before any model
        process existed. The limit's clock starts once one does, so this always tests killing a running model process."""
        def join(self, timeout=None):
            deadline = time.monotonic() + HANG
            while self.name == 'dachapply-analysis' and not model_started() and self.is_alive() and time.monotonic() < deadline:
                time.sleep(.01)
            super().join(timeout)
    monkeypatch.setattr(application_prep, 'Thread', LimitFromModelStart)
    job = _link_job(owner)
    began = time.monotonic()
    assert application_prep._pipeline(job.id, owner.pk) is False
    assert time.monotonic() - began < 5 and application_prep._in_lane == 0
    assert application_prep._state(job, owner)['reason'] == FIT_TIMED_OUT
    [model] = model_started()
    assert model.wait(timeout=5) != 0, 'the model process ended on its own instead of being killed'


@pytest.mark.django_db(transaction=True)
def test_a_run_given_up_after_its_model_answered_saves_nothing(owner, client, fetch, real_threads, monkeypatch):  # noqa: F811
    """Codex review: the model answers in time, but the step after it (here the preview) outlasts the limit."""
    monkeypatch.setattr(application_prep, 'available_model_options', lambda: OPTIONS)
    job = _link_job(owner)
    monkeypatch.setattr(job_evaluator, 'run_structured_model', lambda *a, **k: {'evaluations': [evaluation_for(job, recommendation='apply', fit_score=80)]})
    real_preview = job_evaluator._preview_row
    monkeypatch.setattr(job_evaluator, '_preview_row', lambda *a: (real_threads.wait(HANG), real_preview(*a))[1])
    assert application_prep._pipeline(job.id, owner.pk) is False
    assert application_prep._state(job, owner)['reason'] == FIT_TIMED_OUT
    real_threads.set()
    for worker in [thread for thread in threading.enumerate() if thread.name == 'dachapply-analysis']:
        worker.join(5)
    assert not JobEvaluation.objects.filter(job=job).exists()
    assert application_prep._state(job, owner)['reason'] == FIT_TIMED_OUT


@pytest.mark.django_db(transaction=True)
def test_a_hung_requirements_analysis_fails_with_retry_not_analysing(owner, client, real_threads, monkeypatch):  # noqa: F811
    monkeypatch.setattr(application_prep, 'available_model_options', lambda: OPTIONS)
    monkeypatch.setattr(application_prep, 'run_structured_model', lambda *a, **k: real_threads.wait(HANG))
    job = JobLead.objects.create(company='ACME', title='Python Engineer', status='to_apply', created_by=owner,
                                 original_source_text=POSTING, application_requirements={})
    application_prep._save(job, owner.pk, lambda prep: prep.update(reason=application_prep.ANALYSING, variants={}))
    application_prep._analysing.add(job.id)
    began = time.monotonic()
    assert application_prep._analyse_then_prepare(job.id, owner.pk, False) is False
    assert time.monotonic() - began < 5 and job.id not in application_prep._analysing
    prep = application_prep._state(job, owner)
    assert prep['reason'] == REQUIREMENTS_TIMED_OUT and prep['retry_at'] is None
    assert [item['error'] for item in _items(client) if item['job_id'] == job.id] == [REQUIREMENTS_TIMED_OUT]


# A CLI that starts a long-lived server handing it its stdout/stderr -- `ollama list` on the owner's machine -- then
# prints and exits, or (after) keeps running past the discovery timeout. It prints the server's pid first.
SERVER = (f'import subprocess, sys, time; server = subprocess.Popen([sys.executable, "-c", "import time; time.sleep({HANG})"], '
          'stdout=sys.stdout, stderr=sys.stderr); print(server.pid); print("NAME ID"); print("llama:latest abc"); sys.stdout.flush(); ')


def _kill(pid):
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        pass


def test_model_discovery_returns_although_a_server_it_started_holds_the_output():
    began = time.monotonic()
    result = cv_generator._discovery_run([sys.executable, '-c', SERVER])
    _kill(int(result.stdout.split()[0]))
    assert time.monotonic() - began < 5 and result.returncode == 0 and result.stdout.splitlines()[1:] == ['NAME ID', 'llama:latest abc']
    began = time.monotonic()
    with pytest.raises(subprocess.TimeoutExpired):
        cv_generator._discovery_run([sys.executable, '-c', SERVER + f'time.sleep({HANG})'])
    assert time.monotonic() - began < 5


def test_a_model_cli_timeout_returns_although_its_children_hold_the_output():
    """draft_chat and mailbox_ai run the codex/claude CLI through _run_command with a timeout: the whole tree goes."""
    began = time.monotonic()
    with pytest.raises(subprocess.TimeoutExpired):
        cv_generator._run_command([sys.executable, '-c', SERVER + f'time.sleep({HANG})'], timeout=1, capture_output=True, text=True)
    assert time.monotonic() - began < 10
