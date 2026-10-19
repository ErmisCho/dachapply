"""TASK-312: documents are prepared after an imported evaluation, through one FIFO queue the owner can
see and manage (application_prep._queue, PREP_QUEUE_CONCURRENCY, resume_queue, the queue endpoints).

Hermetic like test_application_prep: the trigger tests run the fake generator in-thread; the queue
tests use `tasks`, a start_cv_task that never finishes by itself, so a test ends a task the way
cv_tasks._run does -- by calling its on_finish -- and can see what is running and what waits.
"""
import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from jobradar.models import JobLead
from jobradar.services import application_prep, cv_tasks, json_importer
from jobradar.tests.test_application_prep import POSTING, _job, _req, client, generator, owner, workspace  # noqa: F401 -- fixtures

QUEUE = '/api/jobs/application-prep/queue/'
ACTION = QUEUE + 'action/'
EVAL = {'fit_score': 80, 'priority': 'high', 'summary': 'fits', 'main_match_reasons': [], 'main_gaps': [], 'required_skills': [],
        'nice_to_have_skills': [], 'matched_skills': [], 'missing_skills': [], 'cv_adjustment_notes': '', 'interview_prep_notes': '',
        'risk_notes': '', 'next_action': ''}


def _evaluate(job, user, recommendation, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        result = json_importer.import_evaluations({'evaluations': [{**EVAL, 'job_id': job.id, 'company': job.company, 'title': job.title,
                                                                    'recommendation': recommendation}]}, user=user)
    assert result['ok'], result


# --- AC1: the trigger ----------------------------------------------------------------------------

@pytest.mark.parametrize('recommendation,status,prepared', [
    ('apply', 'new', True), ('maybe', 'reviewed', True), ('apply', 'to_apply', True),
    ('skip', 'new', False), ('skip', 'to_apply', False), ('apply', 'applied', False), ('maybe', 'interview', False)])
def test_an_imported_evaluation_prepares_open_jobs_unless_it_says_skip(owner, generator, django_capture_on_commit_callbacks, recommendation, status, prepared):
    job = _job(owner, status, requirements=_req('de'))
    _evaluate(job, owner, recommendation, django_capture_on_commit_callbacks)
    assert [call['key'] for call in generator['calls']] == (['cv-de'] if prepared else [])


def test_a_nested_evaluation_in_a_jobs_import_prepares_the_new_job(owner, generator, django_capture_on_commit_callbacks):
    record = {'company': 'Nested', 'title': 'Engineer', 'url': 'https://example.test/nested', 'original_source_text': POSTING,
              'application_requirements': {'posting_language': 'de', 'documents': []}, 'evaluation': {**EVAL, 'recommendation': 'maybe'}}
    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        result = json_importer.import_jobs_data({'jobs': [record]}, user=owner)
        # Nothing starts inside the import's transaction; only its commit does.
        assert result['ok'] and generator['calls'] == []
    assert callbacks and [call['key'] for call in generator['calls']] == ['cv-de']
    assert JobLead.objects.get(pk=result['jobs'][0]['job_id']).status == 'new'


def test_an_evaluation_imported_by_a_non_owner_prepares_nothing(owner, generator, django_capture_on_commit_callbacks):
    stranger = User.objects.create_user('no-cv', password='pw')
    job = JobLead.objects.create(company='Theirs', title='Engineer', created_by=stranger, original_source_text=POSTING, application_requirements=_req('de'))
    _evaluate(job, stranger, 'apply', django_capture_on_commit_callbacks)
    assert generator['calls'] == []


# --- AC2/AC3/AC5: the queue ----------------------------------------------------------------------

@pytest.fixture
def tasks(monkeypatch, generator):
    """start_cv_task that runs nothing: state['end'](task_id, status) finishes one as cv_tasks._run would."""
    state = {'started': [], 'finish': {}, 'live': {}, 'cancelled': []}

    def start(job_id, user_id, context, language, letter_template, create_letter, *choice, create_cv=True, on_finish=None, generation_options=None, **kwargs):
        task_id = f'task-{len(state["started"]) + 1}'
        document = 'cv' if create_cv else 'message' if (generation_options or {}).get('short_message') else 'letter'
        state['started'].append((job_id, f'{document}-{language}'))
        state['finish'][task_id] = on_finish
        state['live'][task_id] = {'status': 'running', 'progress': 40.4, 'estimated_seconds_remaining': 90, 'step_label': '', 'artifacts': {}}
        return task_id

    def end(task_id, status='ready', artifacts=None):
        state['live'][task_id].update(status=status, artifacts=artifacts or {}, error='model failed' if status == 'failed' else '')
        state['finish'][task_id](task_id)

    monkeypatch.setattr(cv_tasks, 'start_cv_task', start)
    monkeypatch.setattr(cv_tasks, 'get_cv_task', lambda task_id, user_id: state['live'].get(task_id))
    monkeypatch.setattr(cv_tasks, 'cancel_cv_task', lambda task_id, user_id: state['cancelled'].append(task_id) or True)
    state['end'] = end
    return state


def _items(client):
    response = client.get(QUEUE)
    assert response.status_code == 200
    return response.json()['items']


def _variant(job, owner, key):
    return application_prep._state(job, owner)['variants'][key]


def test_one_slot_runs_one_task_and_the_next_starts_when_it_finishes(owner, client, tasks, settings):
    first, second = _job(owner, 'new', requirements=_req('de')), _job(owner, 'reviewed', requirements=_req('de'))
    application_prep.prepare(first.id, owner)
    application_prep.prepare(second.id, owner)
    assert tasks['started'] == [(first.id, 'cv-de')]
    assert [(item['job_id'], item['status'], item['position']) for item in _items(client)] == [(first.id, 'running', None), (second.id, 'queued', 1)]
    assert _variant(first, owner, 'cv-de')['started_at'] and not _variant(second, owner, 'cv-de')['started_at']

    tasks['end']('task-1', artifacts={'cv_tex': 'C:/w/CVs/First-CV.tex', 'cv_pdf': 'C:/w/CVs/First-CV.pdf'})
    assert tasks['started'] == [(first.id, 'cv-de'), (second.id, 'cv-de')]
    done = _variant(first, owner, 'cv-de')
    assert done['status'] == 'ready' and done['queued_at'] <= done['started_at'] <= done['finished_at']
    # A failure frees the slot as well.
    third = _job(owner, 'to_apply', requirements=_req('de'))
    application_prep.prepare(third.id, owner)
    tasks['end']('task-2', status='failed')
    assert tasks['started'][-1] == (third.id, 'cv-de') and _variant(second, owner, 'cv-de')['error'] == 'model failed'


def test_the_concurrency_setting_is_the_number_of_running_tasks(owner, tasks, settings):
    settings.PREP_QUEUE_CONCURRENCY = 2
    jobs = [_job(owner, 'new', requirements=_req('de')) for _ in range(3)]
    for job in jobs:
        application_prep.prepare(job.id, owner)
    assert [job_id for job_id, _ in tasks['started']] == [jobs[0].id, jobs[1].id]


def test_manual_generate_is_not_queued(owner, client, tasks, monkeypatch):
    from jobradar import views
    monkeypatch.setattr(views, 'start_cv_task', cv_tasks.start_cv_task)  # the fake; views imported the name
    monkeypatch.setattr(views, 'validate_model_capability', lambda *a, **k: None)
    application_prep.prepare(_job(owner, 'new', requirements=_req('de')).id, owner)
    waiting = _job(owner, 'new', requirements=_req('de'))
    application_prep.prepare(waiting.id, owner)
    manual = _job(owner, 'to_apply', requirements=_req('de'))
    response = client.post(f'/api/jobs/{manual.id}/cv-generation/run/', {'cv_template': 'de', 'create_letter': False, 'provider': 'openai', 'model': 'gpt-6.1', 'effort': 'high'}, format='json')
    # The manual run starts at once although the one slot is taken, and is not counted in the queue.
    assert response.status_code == 202, response.content
    assert tasks['started'][-1] == (manual.id, 'cv-de') and len(tasks['started']) == 2
    assert [item['job_id'] for item in _items(client) if item['status'] == 'queued'] == [waiting.id]


def test_a_restart_requeues_left_variants_in_queued_at_order(owner, client, tasks):
    jobs = [_job(owner, status, requirements=_req('de')) for status in ('new', 'reviewed', 'to_apply', 'to_apply', 'applied')]
    left = [('queued', '', '2026-10-19T10:03:00+00:00'), ('running', 'gone', '2026-10-19T10:01:00+00:00'),
            ('running', 'gone-2', '2026-10-19T10:02:00+00:00'), ('running', 'live-1', '2026-10-19T10:00:00+00:00'),
            ('queued', '', '2026-10-19T09:00:00+00:00')]  # the last job is Applied: not resumed
    for job, (status, task_id, queued_at) in zip(jobs, left):
        application_prep._save(job, owner.pk, lambda prep, status=status, task_id=task_id, queued_at=queued_at: prep.update(
            model={'provider': 'openai', 'model': 'gpt-6.1', 'effort': 'high', 'speed': 'normal'},
            variants={'cv-de': {'document': 'cv', 'language': 'de', 'status': status, 'task_id': task_id, 'error': '', 'files': {}, 'queued_at': queued_at}}))
    tasks['live']['live-1'] = {'status': 'running', 'progress': 10, 'estimated_seconds_remaining': 60, 'step_label': '', 'artifacts': {}}
    # Before the resume the dead run reads as interrupted, as public_state has always said.
    assert application_prep.public_state(jobs[1], owner)['variants'][0]['error'] == application_prep.INTERRUPTED

    assert application_prep.resume_queue() == 3
    # The still-live run is left alone; the rest go oldest first, so the dead run takes the free slot.
    assert tasks['started'] == [(jobs[1].id, 'cv-de')]
    assert application_prep._queue == [(jobs[2].id, owner.pk, 'cv-de'), (jobs[0].id, owner.pk, 'cv-de')]
    state = application_prep.public_state(jobs[1], owner)['variants'][0]
    assert state['status'] == 'running' and state['error'] == ''
    # A dead run that waits for its turn is queued again, no longer "interrupted" anywhere.
    state = application_prep.public_state(jobs[2], owner)['variants'][0]
    assert state['status'] == 'queued' and state['error'] == ''
    assert application_prep.board_summary(jobs[2], owner)['failed'] == 0
    assert [item['status'] for item in _items(client) if item['job_id'] == jobs[2].id] == ['queued']
    # Resuming twice queues nothing twice.
    assert application_prep.resume_queue() == 0


def test_the_restart_resume_runs_only_in_the_serving_process(monkeypatch):
    started = []
    monkeypatch.setattr(application_prep, 'Thread', lambda **kwargs: type('T', (), {'start': lambda self: started.append(kwargs['name'])})())
    assert application_prep.start_queue_resume() is False and started == []  # under pytest, as for the mailbox loop
    from jobradar.services import demo_scheduler
    monkeypatch.setattr(demo_scheduler, 'should_start_local_loop', lambda env_var: env_var == 'DACHAPPLY_PREP_QUEUE_RESUME')
    assert application_prep.start_queue_resume() is True and started == ['dachapply-prep-queue-resume']


def _post(client, job, key, action):
    return client.post(ACTION, {'job_id': job.id, 'key': key, 'action': action}, format='json')


def test_cancel_a_queued_variant_takes_it_out_of_the_queue(owner, client, tasks):
    running, waiting, behind = (_job(owner, 'new', requirements=_req('de')) for _ in range(3))
    for job in (running, waiting, behind):
        application_prep.prepare(job.id, owner)
    response = _post(client, waiting, 'cv-de', 'cancel')
    assert response.status_code == 200
    items = {item['job_id']: item for item in response.json()['items']}
    assert items[waiting.id]['status'] == 'cancelled' and items[waiting.id]['error'] == application_prep.CANCELLED and items[waiting.id]['finished_at']
    assert items[behind.id]['position'] == 1  # moved up into the cancelled one's place
    tasks['end']('task-1')
    assert tasks['started'] == [(running.id, 'cv-de'), (behind.id, 'cv-de')]  # the cancelled one never starts


def test_cancel_a_running_variant_stops_its_task_and_frees_the_slot_when_it_stops(owner, client, tasks):
    running, waiting = _job(owner, 'new', requirements=_req('de')), _job(owner, 'new', requirements=_req('de'))
    for job in (running, waiting):
        application_prep.prepare(job.id, owner)
    assert _post(client, running, 'cv-de', 'cancel').status_code == 200
    assert tasks['cancelled'] == ['task-1'] and _variant(running, owner, 'cv-de')['status'] == 'cancelled'
    assert len(tasks['started']) == 1  # the slot is the task's until its thread ends
    tasks['end']('task-1', status='cancelled')
    assert tasks['started'][-1] == (waiting.id, 'cv-de') and _variant(running, owner, 'cv-de')['status'] == 'cancelled'


def test_retry_puts_a_failed_or_cancelled_variant_at_the_back_of_the_queue(owner, client, tasks):
    jobs = [_job(owner, 'new', requirements=_req('de')) for _ in range(3)]
    for job in jobs:
        application_prep.prepare(job.id, owner)
    tasks['end']('task-1', status='failed')  # jobs[1] starts; jobs[2] waits
    _post(client, jobs[2], 'cv-de', 'cancel')
    for job in (jobs[0], jobs[2]):
        assert _post(client, job, 'cv-de', 'retry').status_code == 200
    queued = [(item['job_id'], item['position']) for item in _items(client) if item['status'] == 'queued']
    assert queued == [(jobs[0].id, 1), (jobs[2].id, 2)]
    retried = _variant(jobs[0], owner, 'cv-de')
    assert retried['error'] == '' and retried['started_at'] is None and retried['finished_at'] is None


def test_first_moves_a_queued_variant_to_the_front(owner, client, tasks):
    jobs = [_job(owner, 'new', requirements=_req('de')) for _ in range(3)]
    for job in jobs:
        application_prep.prepare(job.id, owner)
    response = _post(client, jobs[2], 'cv-de', 'first')
    assert response.status_code == 200
    assert [(item['job_id'], item['position']) for item in response.json()['items'] if item['status'] == 'queued'] == [(jobs[2].id, 1), (jobs[1].id, 2)]
    tasks['end']('task-1')
    assert tasks['started'][-1] == (jobs[2].id, 'cv-de')


def test_actions_that_do_not_fit_answer_400(owner, client, tasks):
    running, waiting = _job(owner, 'new', requirements=_req('de')), _job(owner, 'new', requirements=_req('de'))
    for job in (running, waiting):
        application_prep.prepare(job.id, owner)
    applied = _job(owner, 'applied', requirements=_req('de'))
    application_prep._save(applied, owner.pk, lambda prep: prep.update(variants={'cv-de': {'document': 'cv', 'language': 'de', 'status': 'failed', 'task_id': '', 'error': 'x', 'files': {}}}))
    for job, key, action in ((waiting, 'cv-de', 'explode'), (waiting, 'letter-de', 'cancel'), (running, 'cv-de', 'retry'),
                             (running, 'cv-de', 'first'), (waiting, 'cv-de', 'retry'), (applied, 'cv-de', 'retry')):
        response = _post(client, job, key, action)
        assert response.status_code == 400 and response.json()['detail'], (key, action)
    tasks['end']('task-1')
    for action in ('cancel', 'first'):  # ready
        assert _post(client, running, 'cv-de', action).status_code == 400
    assert client.post(ACTION, {'job_id': 'x', 'key': 'cv-de', 'action': 'cancel'}, format='json').status_code == 400


def test_the_queue_endpoints_are_owner_only(owner, tasks):
    stranger = User.objects.create_user('queue-stranger', password='pw')
    api = APIClient(); api.force_authenticate(stranger)
    assert api.get(QUEUE).status_code == 404
    assert api.post(ACTION, {'job_id': 1, 'key': 'cv-de', 'action': 'cancel'}, format='json').status_code == 404


# --- AC4: the queue page's list ------------------------------------------------------------------

def test_the_queue_lists_running_then_queued_by_position_then_finished_newest_first(owner, client, tasks, settings):
    settings.PREP_QUEUE_CONCURRENCY = 2
    older, newer = _job(owner, 'to_apply', requirements=_req('de')), _job(owner, 'reviewed', requirements=_req('de'))
    application_prep._save(older, owner.pk, lambda prep: prep.update(variants={
        'cv-de': {'document': 'cv', 'language': 'de', 'status': 'ready', 'task_id': '', 'error': '', 'files': {'cv_tex': 'C:/w/CVs/Old-CV.tex', 'cv_pdf': 'C:/w/CVs/Old-CV.pdf'},
                  'queued_at': '2026-10-19T08:00:00+00:00', 'started_at': '2026-10-19T08:00:01+00:00', 'finished_at': '2026-10-19T08:05:00+00:00'}}))
    application_prep._save(newer, owner.pk, lambda prep: prep.update(variants={
        'cv-de': {'document': 'cv', 'language': 'de', 'status': 'failed', 'task_id': '', 'error': 'quota', 'files': {}, 'finished_at': '2026-10-19T09:00:00+00:00'},
        'cv-en': {'document': 'cv', 'language': 'en', 'status': 'ready', 'task_id': '', 'error': '', 'files': {}, 'review': 'discard', 'finished_at': '2026-10-19T09:30:00+00:00'}}))
    active = [_job(owner, 'new', requirements=_req('de', '', cover_letter='required')) for _ in range(2)]
    for job in active:
        application_prep.prepare(job.id, owner)
    application_prep.queue_action(owner, active[1].id, 'letter-de', 'first')

    items = _items(client)
    assert [(item['job_id'], item['key'], item['status'], item['position']) for item in items] == [
        (active[0].id, 'cv-de', 'running', None), (active[0].id, 'letter-de', 'running', None),
        (active[1].id, 'letter-de', 'queued', 1), (active[1].id, 'cv-de', 'queued', 2),
        (newer.id, 'cv-de', 'failed', None), (older.id, 'cv-de', 'ready', None)]  # the discarded cv-en is not listed
    running, ready = items[0], items[-1]
    assert (running['progress'], running['eta_seconds'], running['label'], running['company'], running['job_status']) == (40, 90, 'CV · German', 'ACME', 'new')
    assert (ready['progress'], ready['eta_seconds'], ready['files'], ready['document'], ready['language']) == (100, None, ['Old-CV.tex', 'Old-CV.pdf'], 'cv', 'de')
    assert items[4]['error'] == 'quota' and client.get(QUEUE).json()['concurrency'] == 2
    assert set(running) == {'job_id', 'company', 'title', 'job_status', 'key', 'label', 'document', 'language', 'status', 'position',
                            'progress', 'eta_seconds', 'error', 'files', 'queued_at', 'started_at', 'finished_at', 'retry_at', 'incomplete'}


# --- TASK-317: a usage limit is retried automatically once it resets ----------------------------

RESET = '2026-10-19T18:51:00+02:00'


@pytest.fixture
def timers(monkeypatch):
    """No real timer in tests: each armed one is recorded, and a test calls retry_due itself."""
    armed = []

    class FakeTimer:
        def __init__(self, interval, function):
            self.interval, self.function, self.cancelled = interval, function, False

        def start(self):
            armed.append(self)

        def cancel(self):
            self.cancelled = True
    monkeypatch.setattr(application_prep, 'Timer', FakeTimer)
    monkeypatch.setattr(application_prep, '_timer', None)
    return armed


def _at(monkeypatch, iso):
    from datetime import datetime
    monkeypatch.setattr(application_prep.timezone, 'now', lambda: datetime.fromisoformat(iso))


def _limited(tasks, task_id, reset_at=RESET):
    tasks['live'][task_id].update(status='failed', error='Usage limit reached; resets at 18:51.', usage_limit=True, reset_at=reset_at)
    tasks['finish'][task_id](task_id)


def test_a_usage_limited_variant_is_retried_automatically_once_it_resets(owner, client, tasks, timers, monkeypatch):
    _at(monkeypatch, '2026-10-19T17:00:00+02:00')
    job = _job(owner, 'new', requirements=_req('de'))
    application_prep.prepare(job.id, owner)
    _limited(tasks, 'task-1')
    assert _variant(job, owner, 'cv-de')['retry_at'] == '2026-10-19T18:52:00+02:00'
    assert application_prep._timer[0].isoformat() == '2026-10-19T18:52:00+02:00' and timers[-1].interval == 6720
    item = next(item for item in _items(client) if item['job_id'] == job.id)
    assert item['status'] == 'failed' and item['retry_at'] == '2026-10-19T18:52:00+02:00' and item['error'] == 'Usage limit reached; resets at 18:51.'
    # Before retry_at nothing is re-queued; the timer is armed again for it.
    _at(monkeypatch, '2026-10-19T18:51:59+02:00')
    assert application_prep.retry_due() == 0 and len(tasks['started']) == 1 and application_prep._timer
    _at(monkeypatch, '2026-10-19T18:52:00+02:00')
    assert application_prep.retry_due() == 1
    assert tasks['started'] == [(job.id, 'cv-de'), (job.id, 'cv-de')] and _variant(job, owner, 'cv-de')['auto_retries'] == 1
    assert application_prep._timer is None  # nothing else pending


def test_a_usage_limit_without_a_reset_time_is_retried_half_an_hour_later(owner, tasks, timers, monkeypatch):
    _at(monkeypatch, '2026-10-19T17:00:00+00:00')
    job = _job(owner, 'new', requirements=_req('de'))
    application_prep.prepare(job.id, owner)
    _limited(tasks, 'task-1', reset_at=None)
    assert _variant(job, owner, 'cv-de')['retry_at'] == '2026-10-19T17:30:00+00:00'


def test_automatic_retries_stop_after_three(owner, tasks, timers, monkeypatch):
    _at(monkeypatch, '2026-10-19T17:00:00+02:00')
    job = _job(owner, 'new', requirements=_req('de'))
    application_prep.prepare(job.id, owner)
    for attempt in range(1, 4):
        _limited(tasks, f'task-{attempt}')
        _at(monkeypatch, '2026-10-19T19:00:00+02:00')
        assert application_prep.retry_due() == 1
    _limited(tasks, 'task-4')
    assert _variant(job, owner, 'cv-de')['retry_at'] is None and _variant(job, owner, 'cv-de')['auto_retries'] == 3
    assert application_prep.retry_due() == 0 and len(tasks['started']) == 4


def test_any_other_failure_is_never_retried_automatically(owner, client, tasks, timers, monkeypatch):
    job = _job(owner, 'new', requirements=_req('de'))
    application_prep.prepare(job.id, owner)
    tasks['end']('task-1', status='failed')
    assert _variant(job, owner, 'cv-de')['retry_at'] is None and timers == []
    assert next(item for item in _items(client) if item['job_id'] == job.id)['retry_at'] is None
    _at(monkeypatch, '2099-01-01T00:00:00+00:00')
    assert application_prep.retry_due() == 0 and len(tasks['started']) == 1


def test_a_restart_schedules_pending_usage_limit_retries(owner, tasks, timers, monkeypatch):
    waiting, due = _job(owner, 'new', requirements=_req('de')), _job(owner, 'new', requirements=_req('de'))
    for job, retry_at in ((waiting, '2026-10-19T18:52:00+02:00'), (due, '2026-10-19T16:00:00+02:00')):
        application_prep._save(job, owner.pk, lambda prep, retry_at=retry_at: prep.update(
            model={'provider': 'openai', 'model': 'gpt-6.1', 'effort': 'high', 'speed': 'normal'},
            variants={'cv-de': {'document': 'cv', 'language': 'de', 'status': 'failed', 'task_id': 'gone', 'error': 'Usage limit reached; resets at 18:51.',
                                'files': {}, 'queued_at': '2026-10-19T10:00:00+00:00', 'retry_at': retry_at}}))
    _at(monkeypatch, '2026-10-19T17:00:00+02:00')
    assert application_prep.resume_queue() == 0  # nothing was left queued or running
    assert tasks['started'] == [(due.id, 'cv-de')]  # the one already due is retried at once
    assert application_prep._timer[0].isoformat() == '2026-10-19T18:52:00+02:00'  # the other one is scheduled


def test_a_usage_limited_requirements_analysis_is_retried_automatically(owner, client, tasks, timers, monkeypatch):
    from datetime import datetime
    from jobradar.services.cv_generator import RecoverableGenerationError
    from jobradar.tests.test_application_prep import _model
    _at(monkeypatch, '2026-10-19T17:00:00+02:00')
    monkeypatch.setattr(application_prep, 'fetch_missing_sources', lambda jobs: None)
    job = _job(owner, 'new', requirements={})
    _model(monkeypatch, RecoverableGenerationError('Usage limit reached; resets at 18:51.', usage_limit=True, reset_at=datetime.fromisoformat(RESET)))
    application_prep.prepare(job.id, owner)
    prep = application_prep._state(job, owner)
    assert prep['reason'] == 'Requirements analysis failed: Usage limit reached; resets at 18:51. Press Prepare to retry.'
    assert prep['retry_at'] == '2026-10-19T18:52:00+02:00'
    assert next(item for item in _items(client) if item['job_id'] == job.id)['retry_at'] == '2026-10-19T18:52:00+02:00'
    _model(monkeypatch)
    _at(monkeypatch, '2026-10-19T18:52:00+02:00')
    assert application_prep.retry_due() == 1
    assert tasks['started'] == [(job.id, 'cv-en'), (job.id, 'letter-en')][:len(tasks['started'])] and tasks['started']
    assert application_prep._state(job, owner)['retry_at'] is None
