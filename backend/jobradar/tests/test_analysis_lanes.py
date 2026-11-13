"""TASK-358/360: automatic analyses run analysis_concurrency at a time (application_prep._lane, and the durable units'
shared admission in processing_control), each within the account's analysis_time_limit_minutes, with model discovery
as its own Queue stage; "Use cloud models only" (always, or once from the Queue) starts no local model discovery.

The pipeline runs in real threads here, so the database is committed (transaction=True); every wait is bounded (HANG)
so a broken lane fails a test instead of hanging it.
"""
import threading
import time

import pytest

from jobradar.models import JobEvaluation, JobLead, UserProfile
from jobradar.services import application_prep, cv_generator, job_evaluator
from jobradar.services import processing_control as processing
from jobradar.tests.test_application_prep import POSTING, client, owner, workspace  # noqa: F401 -- fixtures
from jobradar.tests.test_application_prep_queue import ACTION, _items  # noqa: F401
from jobradar.tests.test_job_evaluator import evaluation_for
from jobradar.tests.test_link_only_prep import LINK, fetch  # noqa: F401 -- fixtures

HANG = 20
SKIP = {'ok': True, 'preview': [{'recommendation': 'skip', 'fit_score': 40}]}
OPTIONS = [{'provider': 'openai', 'key': 'gpt-6.1', 'efforts': ['medium'], 'default_effort': 'medium'}]


def _until(predicate, seconds=HANG):
    deadline = time.monotonic() + seconds
    while not predicate():
        assert time.monotonic() < deadline, 'timed out'
        time.sleep(.01)


def _jobs(owner, count):  # noqa: F811
    return [JobLead.objects.create(company='ACME', title=f'Engineer {n}', created_by=owner, url=f'{LINK}?{n}', original_source_text=POSTING)
            for n in range(count)]


def _profile(owner, **fields):  # noqa: F811
    UserProfile.objects.filter(user=owner).update(**fields)


@pytest.fixture
def lanes(monkeypatch, owner, workspace, fetch):  # noqa: F811
    """Real pipeline threads; each fit analysis blocks until its job's gate opens. state: running (job ids in the model
    now), entered (every job that reached it, in order), peak (most at once), gate(job_id), cancelled (job id ->
    the run's cancelled hook)."""
    monkeypatch.setattr(application_prep, 'Thread', threading.Thread)
    monkeypatch.setattr(application_prep, '_piping', set())
    monkeypatch.setattr(application_prep, 'LANE_POLL', .05)
    monkeypatch.setattr(application_prep, 'available_model_options', lambda: OPTIONS)
    lock, gates = threading.Lock(), {}
    state = {'running': set(), 'entered': [], 'peak': 0, 'cancelled': {}, 'gate': lambda job_id: gates.setdefault(job_id, threading.Event())}

    def evaluate(job_ids, user, *args, cancelled=None, **kwargs):
        job_id = job_ids[0]
        with lock:
            state['running'].add(job_id)
            state['entered'].append(job_id)
            state['cancelled'][job_id] = cancelled
            state['peak'] = max(state['peak'], len(state['running']))
        try:
            state['gate'](job_id).wait(HANG)
        finally:
            with lock:
                state['running'].discard(job_id)
        return SKIP
    monkeypatch.setattr(job_evaluator, 'evaluate_jobs', evaluate)
    yield state
    for gate in gates.values():
        gate.set()
    for thread in [thread for thread in threading.enumerate() if thread.name in ('dachapply-pipeline', 'dachapply-analysis')]:
        thread.join(HANG)


def _join_pipelines():
    for thread in [thread for thread in threading.enumerate() if thread.name == 'dachapply-pipeline']:
        thread.join(HANG)


@pytest.mark.django_db(transaction=True)
def test_with_n_lanes_exactly_n_analyses_run_and_the_rest_wait(owner, lanes):  # noqa: F811
    """TASK-358 AC2, counted: N=3 and six jobs waiting -- three in the model at once, three waiting, then all six."""
    _profile(owner, analysis_concurrency=3)
    jobs = _jobs(owner, 6)
    for job in jobs:
        assert application_prep.start_pipeline(job.id, owner, force=True)
    _until(lambda: len(lanes['running']) == 3)
    time.sleep(.3)  # long enough for a fourth to get in, were the lanes not holding it back
    assert len(lanes['running']) == 3 and len(lanes['entered']) == 3 and application_prep._in_lane == 3
    waiting = [job for job in jobs if job.id not in lanes['entered']]
    assert [application_prep._state(job, owner)['pipeline']['stage'] for job in waiting] == ['queued'] * 3
    for job in jobs:
        lanes['gate'](job.id).set()
    _join_pipelines()
    assert lanes['peak'] == 3 and sorted(lanes['entered']) == sorted(job.id for job in jobs) and application_prep._in_lane == 0
    assert {application_prep._state(job, owner)['pipeline']['stage'] for job in jobs} == {'skipped'}


@pytest.mark.django_db(transaction=True)
def test_lowering_n_stops_no_run_and_raising_it_starts_waiting_runs(owner, lanes):  # noqa: F811
    """TASK-358 AC3: N 2 -> 1 leaves both running analyses alone and lets none start when one ends; 1 -> 3 starts both
    waiting runs without a restart."""
    _profile(owner, analysis_concurrency=2)
    jobs = _jobs(owner, 4)
    for job in jobs:
        application_prep.start_pipeline(job.id, owner, force=True)
    _until(lambda: len(lanes['running']) == 2)
    first, second = lanes['entered']
    _profile(owner, analysis_concurrency=1)
    time.sleep(.2)  # past LANE_POLL: the lowered value is what a run reads now
    assert lanes['running'] == {first, second} and not any(cancelled() for cancelled in lanes['cancelled'].values())
    lanes['gate'](first).set()
    _until(lambda: application_prep._state(JobLead.objects.get(pk=first), owner)['pipeline']['stage'] == 'skipped')
    time.sleep(.3)
    assert lanes['running'] == {second} and len(lanes['entered']) == 2  # one lane now, and the running one holds it
    _profile(owner, analysis_concurrency=3)
    _until(lambda: len(lanes['running']) == 3)
    assert len(lanes['entered']) == 4 and not lanes['cancelled'][second]()
    for job in jobs:
        lanes['gate'](job.id).set()
    _join_pipelines()
    assert {application_prep._state(job, owner)['pipeline']['stage'] for job in jobs} == {'skipped'}


@pytest.mark.django_db(transaction=True)
def test_the_daily_limit_holds_whatever_n_and_a_job_never_runs_twice_at_once(owner, lanes):  # noqa: F811
    """TASK-358 AC5: N=5 with a daily budget of 2 and four jobs waiting runs two; a second start of a running job
    starts nothing."""
    _profile(owner, analysis_concurrency=5, daily_analyse_limit=2)
    jobs = _jobs(owner, 4)
    application_prep.run_daily(owner)
    _until(lambda: len(lanes['running']) == 2)
    running = lanes['entered'][0]
    assert application_prep.start_pipeline(running, owner, force=True)  # "already under way"
    application_prep.run_daily(owner)  # the budget is spent
    time.sleep(.3)
    assert len(lanes['entered']) == 2 and lanes['entered'].count(running) == 1
    for job in jobs:
        lanes['gate'](job.id).set()
    _join_pipelines()
    assert len(lanes['entered']) == 2


def test_durable_analyses_share_one_admission_of_n_read_at_each_claim(tmp_path, monkeypatch):
    """TASK-358 AC2/AC3 under the local supervisor: pipeline, requirements and daily-document units share one limit,
    the account's N read at every claim, so a raised N admits a waiting unit without a restart."""
    control = processing.Store(tmp_path / 'control.sqlite3')
    units = [control.enqueue(kind, {'args': [n, 1]}) for n, kind in enumerate(('pipeline', 'requirements', 'daily-document'))]
    assert control.claim(units[0], 'pipeline', 2) and control.claim(units[1], 'requirements', 2)
    assert not control.claim(units[2], 'daily-document', 2)
    lanes, ran = {'n': 2}, threading.Event()
    monkeypatch.setitem(processing._handlers, 'pipeline', lambda *args: ran.set())
    waiting = control.enqueue('pipeline', {'args': [9, 1], 'kwargs': {}})
    worker = threading.Thread(target=processing.execute, args=(control, waiting, 'pipeline', [9, 1], {}, lambda job_id, user_id: lanes['n']), daemon=True)
    worker.start()
    assert not ran.wait(.5)
    lanes['n'] = 3
    assert ran.wait(5)
    worker.join(5)


@pytest.mark.django_db(transaction=True)
def test_the_time_limit_is_the_profiles_minutes_and_its_wording_says_so(owner, client, lanes, monkeypatch):  # noqa: F811
    """TASK-360 AC1: 2 minutes on the Profile page (one "minute" lasts .25 s here) end a hung run after .5 s -- not the
    old fixed 10 minutes' 2.5 s -- with that wording."""
    _profile(owner, analysis_time_limit_minutes=2)
    monkeypatch.setattr(application_prep, 'MINUTE', .25)
    [job] = _jobs(owner, 1)
    began = time.monotonic()
    assert application_prep._pipeline(job.id, owner.pk) is False
    assert .4 < time.monotonic() - began < 2 and lanes['cancelled'][job.id]()
    assert application_prep._state(job, owner)['reason'] == 'Analysis failed: Stopped after 2 minutes, the time limit for one analysis. Press Retry.'


@pytest.mark.django_db(transaction=True)
def test_finding_models_is_its_own_stage_before_fetching_and_analysing(owner, client, lanes, monkeypatch):  # noqa: F811
    """TASK-360 AC2: while the models are looked for, the Queue lists the run as Finding models, from when it began."""
    [job] = _jobs(owner, 1)
    seen = []

    def discover():
        [item] = [item for item in _items(client) if item['job_id'] == job.id]
        seen.append((item['label'], item['stage'], item['status'], item['started_at'] == application_prep._state(job, owner)['pipeline']['at'], item['cloud_retry']))
        return OPTIONS
    monkeypatch.setattr(application_prep, 'available_model_options', discover)
    fetch_sources = application_prep.fetch_missing_sources
    monkeypatch.setattr(application_prep, 'fetch_missing_sources', lambda jobs, **kw: (seen.append(application_prep._state(job, owner)['pipeline']['stage']), fetch_sources(jobs, **kw))[1])
    lanes['gate'](job.id).set()
    application_prep._pipeline(job.id, owner.pk)
    assert seen == [('Finding models', 'models', 'running', True, True), 'fetching']
    assert lanes['entered'] == [job.id] and application_prep._state(job, owner)['pipeline']['stage'] == 'skipped'


@pytest.mark.parametrize('stage', ['analysing', 'requirements', 'queued'])
@pytest.mark.parametrize('account_cloud,run_cloud,rerun,offered', [
    (False, False, False, True), (True, True, False, False),
    (False, True, False, False), (True, False, False, True),
    (False, False, True, False), (True, None, False, False),
])
def test_queue_cloud_retry_matches_the_active_run(owner, client, workspace, monkeypatch, stage, account_cloud, run_cloud, rerun, offered):
    [job] = _jobs(owner, 1)
    _profile(owner, use_cloud_models_only=account_cloud)
    application_prep._save(job, owner.pk, lambda prep: prep.update(
        pipeline={'stage': stage, 'at': application_prep._now()}, reason=''))
    monkeypatch.setattr(application_prep, '_stops', {} if run_cloud is None else {job.id: (threading.Event(), run_cloud)})
    monkeypatch.setattr(application_prep, '_cloud_rerun', {job.id} if rerun else set())
    [item] = _items(client)
    assert item['cloud_retry'] is offered


# --- TASK-360: cloud models only ------------------------------------------------------------------------------------

@pytest.fixture
def machine(monkeypatch):
    """Every CLI is "installed"; a local discovery process (ollama list, lms ls) is recorded instead of started -- and
    fails, as a broken local install would -- and the cloud CLIs are there while state['cloud']."""
    state = {'discovered': [], 'cloud': True}

    def discovery(command):
        state['discovered'].append(command[1:])
        raise OSError('no local model process in tests')
    monkeypatch.setattr(cv_generator.shutil, 'which', lambda name: None if name.startswith(('codex', 'claude')) and not state['cloud'] else f'/bin/{name}')
    monkeypatch.setattr(cv_generator, '_discovery_run', discovery)
    return state


@pytest.fixture
def cloud_model(monkeypatch):
    """The fit analysis through the real evaluate_jobs and model discovery; the model's answer is canned, its provider
    recorded."""
    providers = []

    def run(prompt, schema, provider, *args, **kwargs):
        providers.append(provider)
        return {'evaluations': [evaluation_for(JobLead.objects.get(pk=state['job']), recommendation='skip', fit_score=44)]}
    state = {'providers': providers}
    monkeypatch.setattr(job_evaluator, 'run_structured_model', run)
    monkeypatch.setattr(application_prep, 'Thread', threading.Thread)
    monkeypatch.setattr(application_prep, '_piping', set())
    return state


@pytest.mark.django_db(transaction=True)
def test_the_cloud_only_switch_starts_no_local_discovery_for_analysis_or_generation(owner, client, workspace, fetch, machine, cloud_model):  # noqa: F811
    """TASK-360 AC3. The control first: with the switch off, discovery does start ollama and lms."""
    [job] = _jobs(owner, 1)
    cloud_model['job'] = job.id
    cv_generator.available_model_options()
    assert machine['discovered'] == [['list'], ['ls', '--llm', '--json']]
    machine['discovered'].clear()
    cv_generator._model_options_cache.update(at=0.0, options=None)
    _profile(owner, use_cloud_models_only=True)
    assert application_prep._pipeline(job.id, owner.pk) is True
    assert cloud_model['providers'] == ['openai'] and JobEvaluation.objects.filter(job=job).exists()
    preview = cv_generator.generation_preview(job, owner)
    assert {model['provider'] for model in preview['models']} == {'openai', 'anthropic'} and preview['default_pick']['provider'] == 'openai'
    with cv_generator.cloud_models_only(cv_generator.uses_cloud_only(owner.pk)):  # generate_cv_package's check
        cv_generator.validate_model_capability('openai', preview['default_pick']['model'], preview['default_pick']['effort'], 'normal', needs_tools=True)
    assert machine['discovered'] == []


@pytest.mark.django_db(transaction=True)
def test_cloud_only_this_time_reruns_a_failed_analysis_and_leaves_the_switch_off(owner, client, workspace, fetch, machine, cloud_model):  # noqa: F811
    """TASK-360 AC4, a failed analysis: the Queue offers it, and it runs again with a cloud model, the switch off."""
    [job] = _jobs(owner, 1)
    cloud_model['job'] = job.id
    application_prep._save(job, owner.pk, lambda prep: prep.update(pipeline={'stage': 'failed', 'at': 'T', 'error': 'x', 'note': ''}, reason='Analysis failed: x. Press Retry.'))
    [item] = _items(client)
    assert item['cloud_retry'] is True
    assert client.post(ACTION, {'job_id': job.id, 'key': '', 'action': 'cloud'}, format='json').status_code == 200
    _join_pipelines()
    assert cloud_model['providers'] == ['openai'] and machine['discovered'] == []
    assert application_prep._state(job, owner)['pipeline']['stage'] == 'skipped'
    assert UserProfile.objects.get(user=owner).use_cloud_models_only is False


@pytest.mark.django_db(transaction=True)
def test_cloud_only_this_time_stops_an_analysis_stuck_finding_models_and_runs_it_again(owner, client, workspace, fetch, machine, cloud_model, monkeypatch):  # noqa: F811
    """TASK-360 AC4, a running analysis -- stuck in local model discovery, as TASK-357's was: the Queue's action gives the
    run up at once (no waiting for the time limit) and the job is analysed again with a cloud model, no discovery."""
    [job] = _jobs(owner, 1)
    cloud_model['job'] = job.id
    stuck, release = threading.Event(), threading.Event()
    discoveries = []

    def discover():
        discoveries.append(1)
        stuck.set()
        release.wait(HANG)
        return []
    monkeypatch.setattr(cv_generator, '_discover_model_options', discover)
    application_prep.start_pipeline(job.id, owner, force=True)
    try:
        assert stuck.wait(HANG)
        [item] = _items(client)
        assert (item['status'], item['label'], item['cloud_retry']) == ('running', 'Finding models', True)
        began = time.monotonic()
        assert client.post(ACTION, {'job_id': job.id, 'key': '', 'action': 'cloud'}, format='json').status_code == 200
        _until(lambda: JobEvaluation.objects.filter(job=job).exists())
        _join_pipelines()
        assert time.monotonic() - began < 5  # well inside the 5-minute limit: stopped, not timed out
    finally:
        release.set()
    assert discoveries == [1] and machine['discovered'] == [] and cloud_model['providers'] == ['openai']
    prep = application_prep._state(job, owner)
    assert prep['pipeline']['stage'] == 'skipped' and prep['reason'] == ''
    assert UserProfile.objects.get(user=owner).use_cloud_models_only is False


@pytest.mark.django_db(transaction=True)
def test_cloud_only_this_time_reruns_a_failed_requirements_analysis(owner, client, workspace, fetch, machine, cloud_model, monkeypatch):  # noqa: F811
    """TASK-360 AC4 for the other automatic analysis: a failed requirements analysis runs again with a cloud model."""
    providers = []

    def run(prompt, schema, provider, *args, **kwargs):  # stops right after the model choice: no documents follow
        providers.append(provider)
        raise RuntimeError('canned stop')
    monkeypatch.setattr(application_prep, 'run_structured_model', run)
    job = JobLead.objects.create(company='ACME', title='Python Engineer', status='to_apply', created_by=owner, original_source_text=POSTING, application_requirements={})
    application_prep._save(job, owner.pk, lambda prep: prep.update(reason=f'{application_prep.REQUIREMENTS_FAILED}: x. Press Prepare to retry.', variants={}))
    [item] = _items(client)
    assert item['cloud_retry'] is True
    assert client.post(ACTION, {'job_id': job.id, 'key': '', 'action': 'cloud'}, format='json').status_code == 200
    _until(lambda: job.id not in application_prep._analysing)
    assert providers == ['openai'] and machine['discovered'] == []
    assert application_prep._state(job, owner)['reason'] == f'{application_prep.REQUIREMENTS_FAILED}: canned stop. Press Prepare to retry.'


@pytest.mark.django_db(transaction=True)
def test_with_no_cloud_model_both_cloud_options_say_so(owner, client, workspace, fetch, machine, cloud_model):  # noqa: F811
    """TASK-360 AC5: the Queue's action refuses with the reason, the Profile page knows, and an analysis with the switch
    on fails saying so -- none of them looks for a local model instead."""
    machine['cloud'] = False
    [job] = _jobs(owner, 1)
    application_prep._save(job, owner.pk, lambda prep: prep.update(pipeline={'stage': 'failed', 'at': 'T', 'error': 'x', 'note': ''}, reason='Analysis failed: x. Press Retry.'))
    response = client.post(ACTION, {'job_id': job.id, 'key': '', 'action': 'cloud'}, format='json')
    assert response.status_code == 400 and response.json()['detail'] == f'{application_prep.NO_CLOUD}.'
    assert client.get('/api/profile/').json()['cloud_models_available'] is False
    _profile(owner, use_cloud_models_only=True)
    assert application_prep._pipeline(job.id, owner.pk) is False
    assert application_prep._state(job, owner)['reason'] == f'Analysis failed: {application_prep.NO_CLOUD}. Press Retry.'
    assert machine['discovered'] == [] and cloud_model['providers'] == []


# TASK-375 TASK-376: real worker stop, late completion, and durable restart with no lost posting.
@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize('action', ['skip', 'cancel'])
def test_queue_stops_analysis_and_cancel_survives_restart(owner, client, lanes, monkeypatch, action):
    job = _jobs(owner, 1)[0]
    application_prep.start_pipeline(job.id, owner, force=True, reanalyse=application_prep.REANALYSED)
    _until(lambda: job.id in lanes['entered'])
    response = client.post(ACTION, {'job_id':job.id, 'key':'', 'action':action}, format='json')
    assert response.status_code == 200, response.data
    assert application_prep._state(job, owner)['pipeline']['note'] == application_prep.REANALYSED  # TASK-376
    _until(lambda: lanes['cancelled'][job.id]())
    _join_pipelines()
    assert application_prep._state(job, owner)['pipeline']['stage'] == ('skipped' if action == 'skip' else 'cancelled')
    lanes['gate'](job.id).set()
    if action == 'cancel':
        monkeypatch.setattr(application_prep, '_stops', {})
        application_prep.resume_queue()
        assert [row['status'] for row in _items(client) if row['job_id'] == job.id] == ['cancelled']
        response = client.post(ACTION, {'job_id':job.id, 'key':'', 'action':'restart'}, format='json')
        assert response.status_code == 200, response.data
        _join_pipelines()
        assert lanes['entered'] == [job.id, job.id]
    else:
        application_prep.run_daily(owner)
        assert lanes['entered'] == [job.id]
    job.refresh_from_db()
    assert job.original_source_text == POSTING
