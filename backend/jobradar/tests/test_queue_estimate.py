"""TASK-340: the Queue's time estimate -- analysis durations measured into cv-benchmarks.jsonl, a median per
route and model with a named fallback, and the lanes (fit analyses one at a time, requirements analyses
beside them, documents PREP_QUEUE_CONCURRENCY at a time) that give each item's finish time and the total.
"""
from datetime import datetime, timedelta

import pytest

from jobradar.services import application_prep, cv_tasks
from jobradar.tests.test_application_prep import _job, _req, client, generator, owner, workspace  # noqa: F401 -- fixtures
from jobradar.tests.test_application_prep_queue import _at, tasks  # noqa: F401 -- fixtures
from jobradar.tests.test_auto_pipeline import _add, model  # noqa: F401 -- fixtures
from jobradar.tests.test_link_only_prep import fetch  # noqa: F401 -- fixtures

NOW = '2026-10-22T10:00:00+00:00'


def _ago(seconds):
    return (datetime.fromisoformat(NOW) - timedelta(seconds=seconds)).isoformat()


def test_the_estimate_is_the_median_of_the_newest_runs_of_the_model_last_used(workspace):
    assert cv_tasks.measured_seconds('fit') is None
    for seconds in (900, 900, 900, *range(100, 120)):  # the three oldest fall outside the newest ANALYSIS_RUNS
        cv_tasks.record_duration('fit', 'openai', 'gpt-6.1-sol', 'high', seconds)
    cv_tasks.record_duration('requirements', 'openai', 'gpt-6.1-sol', 'high', 40)
    assert cv_tasks.measured_seconds('fit') == 109.5 and cv_tasks.measured_seconds('requirements') == 40
    cv_tasks.record_duration('fit', 'openai', 'gpt-7', 'high', 300)  # a new default model: only its own runs count
    assert cv_tasks.measured_seconds('fit') == 300
    # The document estimate never reads analysis rows.
    assert cv_tasks._learned_timing(('openai', 'gpt-6.1-sol', 'high', 'normal', True, False, False))[1] == 'none'


def test_both_analyses_record_their_duration_where_they_finish(owner, client, tasks, fetch, model, django_capture_on_commit_callbacks):
    model['answers'] = ['apply']
    _add(client, django_capture_on_commit_callbacks)  # fit analysis, then the hook's requirements analysis
    assert cv_tasks.measured_seconds('fit') is not None and cv_tasks.measured_seconds('requirements') is not None


@pytest.fixture
def board(owner, workspace, monkeypatch, settings):
    """Two fit analyses (one running for 30 s, one waiting), a requirements analysis 10 s in, one CV running
    with 50 s left, a CV and a letter queued, and a CV finished today."""
    _at(monkeypatch, NOW)
    monkeypatch.setattr(application_prep, '_queue', [])
    jobs = [_job(owner, 'new', requirements=_req('de')) for _ in range(5)]
    save = application_prep._save
    save(jobs[0], owner.pk, lambda prep: prep.update(pipeline={'stage': 'analysing', 'at': _ago(30)}))
    save(jobs[1], owner.pk, lambda prep: prep.update(pipeline={'stage': 'queued', 'at': _ago(90)}))
    save(jobs[2], owner.pk, lambda prep: prep.update(reason=application_prep.ANALYSING, analysing_at=_ago(10)))
    monkeypatch.setattr(application_prep, '_analysing', {jobs[2].id})  # a daily-batch run: no pipeline stage
    choice = {'provider': 'openai', 'model': 'gpt-6.1-sol', 'effort': 'high', 'speed': 'normal'}

    def variant(status, document, at, **extra):
        return {'document': document, 'language': 'de', 'status': status, 'task_id': '', 'error': '', 'files': {},
                'queued_at': at, 'started_at': None, 'finished_at': None, **extra}
    save(jobs[3], owner.pk, lambda prep: prep.update(model=choice, variants={
        'cv-de': variant('running', 'cv', _ago(300), task_id='t1'), 'letter-de': variant('queued', 'letter', _ago(300))}))
    save(jobs[4], owner.pk, lambda prep: prep.update(model=choice, variants={
        'cv-de': variant('queued', 'cv', _ago(200)), 'cv-en': variant('ready', 'cv', _ago(900), finished_at=_ago(600))}))
    monkeypatch.setattr(cv_tasks, 'get_cv_task', lambda task_id, user_id: {'progress': 60, 'estimated_seconds_remaining': 50} if task_id == 't1' else None)
    calls = []

    def estimate(provider, model, effort, speed, create_cv=True, create_letter=True, is_revision=False):
        calls.append((provider, model, effort, speed, create_cv, create_letter))
        return {'seconds': 100 if create_cv else 60, 'history': 'measured'}
    monkeypatch.setattr(cv_tasks, 'estimate_seconds', estimate)
    return {'jobs': jobs, 'calls': calls}


def _etas(owner, board):
    state = application_prep.queue_state(owner)
    ids = {job.id: index for index, job in enumerate(board['jobs'])}
    return {(ids[item['job_id']], item['key']): item['eta_seconds'] for item in state['items']}, state['summary']


def test_without_history_the_fallback_defaults_are_used_and_lanes_run_side_by_side(owner, board, settings):
    settings.PREP_QUEUE_CONCURRENCY = 1
    etas, summary = _etas(owner, board)
    fit, requirements = application_prep.ANALYSIS_SECONDS['fit'], application_prep.ANALYSIS_SECONDS['requirements']
    # Fit lane: the running one has 120 - 30 left, the waiting one follows it; requirements beside them.
    assert etas[(0, '')] == fit - 30 and etas[(1, '')] == 2 * fit - 30 and etas[(2, '')] == requirements - 10
    # Document lane, one at a time in queue order: running 50, then the letter (60), then the CV (100).
    assert (etas[(3, 'cv-de')], etas[(3, 'letter-de')], etas[(4, 'cv-de')]) == (50, 110, 210)
    assert etas[(4, 'cv-en')] is None
    # The queued variants were estimated with the model they will run with, as their document kind.
    assert board['calls'] == [('openai', 'gpt-6.1-sol', 'high', 'normal', False, True), ('openai', 'gpt-6.1-sol', 'high', 'normal', True, False)]
    assert summary == {'done': 1, 'total': 7, 'analyses_left': 3, 'documents_left': 3, 'seconds_left': 210}


def test_measured_history_and_more_document_slots_change_the_lanes(owner, board, settings):
    settings.PREP_QUEUE_CONCURRENCY = 2
    for seconds in (190, 200, 210):
        cv_tasks.record_duration('fit', 'openai', 'gpt-6.1-sol', 'high', seconds)
    cv_tasks.record_duration('requirements', 'openai', 'gpt-6.1-sol', 'high', 45)
    etas, summary = _etas(owner, board)
    assert (etas[(0, '')], etas[(1, '')], etas[(2, '')]) == (170, 370, 35)
    # Two slots: the letter starts at once beside the running CV, the queued CV when the running one ends.
    assert (etas[(3, 'cv-de')], etas[(3, 'letter-de')], etas[(4, 'cv-de')]) == (50, 60, 150)
    assert summary['seconds_left'] == 370  # the fit lane ends last


def test_an_idle_queue_has_nothing_left(owner, workspace):
    assert application_prep.queue_state(owner)['summary'] == {'done': 0, 'total': 0, 'analyses_left': 0, 'documents_left': 0, 'seconds_left': 0}
