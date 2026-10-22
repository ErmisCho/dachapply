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
    cv_tasks.record_duration('fit', 'openai', 'gpt-7', 'xhigh', 500)  # and a new effort only its own
    assert cv_tasks.measured_seconds('fit') == 500
    # The document estimate never reads analysis rows.
    assert cv_tasks._learned_timing(('openai', 'gpt-6.1-sol', 'high', 'normal', True, False, False))[1] == 'none'


def test_a_degenerate_run_is_not_recorded(workspace):
    cv_tasks.record_duration('fit', 'openai', 'gpt-6.1-sol', 'high', cv_tasks.MIN_ANALYSIS_SECONDS - .1)
    assert cv_tasks.measured_seconds('fit') is None


def test_both_analyses_record_their_duration_the_fit_run_with_its_fetch(owner, client, tasks, fetch, model, monkeypatch, django_capture_on_commit_callbacks):
    clock, seen = [1000.0], []
    monkeypatch.setattr(application_prep.time, 'monotonic', lambda: clock[0])

    fetch_sources = application_prep.fetch_missing_sources

    def fetching(jobs):  # 30 s of fetching, under a stage that already carries the run's start
        seen.append(application_prep._state(jobs[0], owner)['pipeline'])
        clock[0] += 30
        return fetch_sources(jobs)
    monkeypatch.setattr(application_prep, 'fetch_missing_sources', fetching)
    evaluate = application_prep.job_evaluator.evaluate_jobs

    def analysing(job_ids, user, *args, **kwargs):  # 60 s in the model
        seen.append(application_prep._state(application_prep.JobLead.objects.get(pk=job_ids[0]), owner)['pipeline'])
        clock[0] += 60
        return evaluate(job_ids, user, *args, **kwargs)
    monkeypatch.setattr(application_prep.job_evaluator, 'evaluate_jobs', analysing)

    def requirements(*args, **kwargs):  # 20 s for the requirements
        clock[0] += 20
        return {'application_requirements': _req('de')}
    monkeypatch.setattr(application_prep, 'run_structured_model', requirements)
    model['answers'] = ['apply']
    _add(client, django_capture_on_commit_callbacks)
    assert [stage['stage'] for stage in seen] == ['fetching', 'analysing'] and seen[0]['started'] == seen[1]['started']
    assert cv_tasks.measured_seconds('fit') >= 90 and cv_tasks.measured_seconds('requirements') == 20


@pytest.fixture
def board(owner, workspace, monkeypatch, settings):
    """Two fit analyses (one 30 s into its run, 5 s of it analysing; one waiting), a requirements analysis 10 s
    in, one CV running with 50 s left, a CV and a letter queued, and finished today: a ready CV, a failed letter,
    a cancelled message, and a ready CV of a job moved to Applied."""
    _at(monkeypatch, NOW)
    monkeypatch.setattr(application_prep, '_queue', [])
    jobs = [_job(owner, 'new', requirements=_req('de')) for _ in range(5)]
    save = application_prep._save
    save(jobs[0], owner.pk, lambda prep: prep.update(pipeline={'stage': 'analysing', 'at': _ago(5), 'started': _ago(30)}))
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
        'cv-de': variant('queued', 'cv', _ago(200)), 'cv-en': variant('ready', 'cv', _ago(900), finished_at=_ago(600)),
        'letter-en': variant('failed', 'letter', _ago(900), finished_at=_ago(500)), 'message-en': variant('cancelled', 'message', _ago(900), finished_at=_ago(400))}))
    applied = _job(owner, 'applied', requirements=_req('de'))
    save(applied, owner.pk, lambda prep: prep.update(variants={'cv-de': variant('ready', 'cv', _ago(900), finished_at=_ago(700))}))
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
    assert etas[(4, 'cv-en')] is None and etas[(4, 'letter-en')] is None
    # The queued variants were estimated with the model they will run with, as their document kind.
    assert board['calls'] == [('openai', 'gpt-6.1-sol', 'high', 'normal', False, True), ('openai', 'gpt-6.1-sol', 'high', 'normal', True, False)]
    # Done: the ready CV and the Applied job's -- not the failed letter nor the cancelled message.
    assert summary == {'done': 2, 'total': 8, 'analyses_left': 3, 'documents_left': 3, 'seconds_left': 210}


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


def test_a_fit_run_counts_its_fetch_and_an_old_sidecar_its_stage(owner, workspace, monkeypatch):
    _at(monkeypatch, NOW)
    fetching, legacy = _job(owner, 'new'), _job(owner, 'new')
    application_prep._save(fetching, owner.pk, lambda prep: prep.update(pipeline={'stage': 'fetching', 'at': _ago(40), 'started': _ago(40)}))
    application_prep._save(legacy, owner.pk, lambda prep: prep.update(pipeline={'stage': 'analysing', 'at': _ago(70)}))
    etas = {item['job_id']: item['eta_seconds'] for item in application_prep.queue_state(owner)['items']}
    fit = application_prep.ANALYSIS_SECONDS['fit']
    # One lane: the legacy run (older stage stamp) holds the lock first, the fetching one is scheduled after it.
    assert sorted(etas.values()) == [fit - 70, fit - 70 + fit - 40]


def test_a_requirements_analysis_shows_only_while_it_runs_and_never_over_a_fit_run(owner, workspace, monkeypatch):
    _at(monkeypatch, NOW)
    stopped, refit = _job(owner, 'new'), _job(owner, 'new')
    # A restart stopped this one: still marked Analysing in the sidecar, but no thread runs it.
    application_prep._save(stopped, owner.pk, lambda prep: prep.update(pipeline={'stage': 'analysed', 'at': _ago(60)}, reason=application_prep.ANALYSING, variants={}))
    # This one's requirements are analysed while its fit analysis waits to run again: it stays in the fit lane.
    application_prep._save(refit, owner.pk, lambda prep: prep.update(pipeline={'stage': 'queued', 'at': _ago(60)}, reason=application_prep.ANALYSING, variants={}))
    monkeypatch.setattr(application_prep, '_analysing', {refit.id})
    state = application_prep.queue_state(owner)
    assert [(item['job_id'], item['label'], item['eta_seconds']) for item in state['items']] == [(refit.id, 'Waiting to analyse', application_prep.ANALYSIS_SECONDS['fit'])]
    assert state['summary']['analyses_left'] == 1


def test_a_short_message_is_estimated_as_cv_tasks_runs_it_a_letter_document(monkeypatch):
    # application_prep._start starts a message with create_letter=True (short_message is only a generation option),
    # so cv_tasks times it, compiles it and records its benchmark rows under the letter's key: the same estimate.
    calls = []
    monkeypatch.setattr(cv_tasks, 'estimate_seconds', lambda *args, **kwargs: calls.append((args, kwargs)) or {'seconds': 1})
    for document in ('message', 'letter'):
        application_prep._document_seconds({'model': {'provider': 'openai', 'model': 'm', 'effort': 'high', 'speed': 'normal'}}, {'document': document})
    assert calls[0] == calls[1] == (('openai', 'm', 'high', 'normal'), {'create_cv': False, 'create_letter': True})
