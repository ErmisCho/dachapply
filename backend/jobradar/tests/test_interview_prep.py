"""TASK-355: moving a job to Interview gives prep notes. Each run costs money, so these tests count calls
of a fake model rather than notes. Nothing here reaches a real provider."""
import pytest
from django.contrib.auth.models import User
from django.db import connection
from django.test.utils import CaptureQueriesContext

from jobradar.models import ApplicationNote, JobEvaluation, MailboxMessage, MailboxRun, MailboxSuggestion
from jobradar.services import application_prep, interview_prep, mailbox, processing_control
from jobradar.tests.test_application_prep import POSTING, SyncThread, _job, _move, client, owner, workspace  # noqa: F401 -- fixtures

NOTES = {'what_to_study': ['Django internals, the role leans on them'], 'likely_questions': ['How would you scale these APIs?']}


class HeldThread:
    """A started run that has not finished: the job stays in _active until the test releases it."""
    held = []

    def __init__(self, target, args=(), name='', daemon=None):
        self.target, self.args = target, args

    def start(self):
        self.held.append(self)


@pytest.fixture
def model(monkeypatch, workspace):
    state = {'prompts': [], 'fail': None}

    def run(prompt, schema, *args, **kwargs):
        state['prompts'].append(prompt)
        if state['fail']:
            raise RuntimeError(state['fail'])
        return NOTES

    monkeypatch.setattr(interview_prep, 'run_structured_model', run)
    monkeypatch.setattr(interview_prep, 'available_model_options', lambda: [{'provider': 'openai', 'key': 'gpt-test', 'efforts': [], 'default_effort': ''}])
    monkeypatch.setattr(interview_prep, 'cv_default_choice', lambda options: (options[0], 'high'))
    monkeypatch.setattr(interview_prep, 'validate_model_capability', lambda *args, **kwargs: {})
    monkeypatch.setattr(interview_prep, 'load_candidate_evidence', lambda profile, *args: 'CANDIDATE EVIDENCE: shipped payments APIs')
    monkeypatch.setattr(interview_prep, 'Thread', SyncThread)
    interview_prep._active.clear()
    HeldThread.held.clear()
    yield state
    interview_prep._active.clear()


def _url(job):
    return f'/api/jobs/{job.id}/interview-prep/'


def _prep_notes(job):
    return ApplicationNote.objects.filter(job=job, note_type='interview_prep')


def test_entering_interview_writes_one_grounded_note_in_two_labelled_parts(client, owner, model, django_capture_on_commit_callbacks):
    job = _job(owner, 'applied')
    JobEvaluation.objects.create(job=job, fit_score=71, priority='high', recommendation='apply', summary='EVALUATION SUMMARY', main_gaps=['Kubernetes'])
    _move(client, job, 'interview', django_capture_on_commit_callbacks)

    assert len(model['prompts']) == 1
    for grounded in (POSTING, 'EVALUATION SUMMARY', 'Kubernetes', 'CANDIDATE EVIDENCE'):
        assert grounded in model['prompts'][0]
    note = _prep_notes(job).get()
    assert note.note.startswith('What to study\n- Django internals')
    assert '\n\nLikely questions\n- How would you scale' in note.note
    assert client.get(_url(job)).data['status'] == 'ready'


def test_refreshing_or_moving_out_and_back_never_runs_the_model_twice(client, owner, model, django_capture_on_commit_callbacks):
    job = _job(owner, 'applied')
    _move(client, job, 'interview', django_capture_on_commit_callbacks)
    assert len(model['prompts']) == 1

    client.get(_url(job))
    _move(client, job, 'applied', django_capture_on_commit_callbacks)
    _move(client, job, 'interview', django_capture_on_commit_callbacks)
    client.post(_url(job) + 'run/', {}, format='json')  # a stale tab's Prep notes button

    assert len(model['prompts']) == 1
    assert _prep_notes(job).count() == 1


def test_nothing_starts_a_second_run_while_one_is_going(client, owner, model, monkeypatch, django_capture_on_commit_callbacks):
    monkeypatch.setattr(interview_prep, 'Thread', HeldThread)
    job = _job(owner, 'applied')
    _move(client, job, 'interview', django_capture_on_commit_callbacks)
    assert client.get(_url(job)).data['status'] == 'queued'

    client.post(_url(job) + 'run/', {}, format='json')
    client.post(_url(job) + 'run/', {'regenerate': True}, format='json')
    _move(client, job, 'applied', django_capture_on_commit_callbacks)
    _move(client, job, 'interview', django_capture_on_commit_callbacks)

    assert len(HeldThread.held) == 1
    HeldThread.held[0].target(*HeldThread.held[0].args)
    assert len(model['prompts']) == 1
    assert client.get(_url(job)).data['status'] == 'ready'


def test_a_job_already_in_interview_generates_on_request(client, owner, model):
    job = _job(owner, 'interview')
    assert client.get(_url(job)).data == {'status': 'idle', 'error': '', 'note': None}
    assert client.post(_url(job) + 'run/', {}, format='json').data['status'] == 'ready'
    assert len(model['prompts']) == 1


def test_a_failure_shows_and_waits_for_retry(client, owner, model, django_capture_on_commit_callbacks):
    model['fail'] = 'provider down'
    job = _job(owner, 'applied')
    _move(client, job, 'interview', django_capture_on_commit_callbacks)
    state = client.get(_url(job)).data
    assert (state['status'], state['error']) == ('failed', 'provider down')

    _move(client, job, 'offer', django_capture_on_commit_callbacks)
    _move(client, job, 'interview', django_capture_on_commit_callbacks)
    client.get(_url(job))
    assert len(model['prompts']) == 1  # neither a refresh nor a move spends on it again

    model['fail'] = None
    assert client.post(_url(job) + 'run/', {}, format='json').data['status'] == 'ready'
    assert len(model['prompts']) == 2


def test_only_regenerate_replaces_a_note_and_a_failed_one_keeps_it(client, owner, model):
    job = _job(owner, 'interview')
    client.post(_url(job) + 'run/', {}, format='json')
    note = _prep_notes(job).get()

    client.post(_url(job) + 'run/', {'regenerate': 'true'}, format='json')  # only a JSON true presses it
    assert len(model['prompts']) == 1

    model['fail'] = 'provider down'
    state = client.post(_url(job) + 'run/', {'regenerate': True}, format='json').data
    assert state['status'] == 'failed' and state['note']['note'] == note.note

    model['fail'] = None
    NOTES_BEFORE = dict(NOTES)
    NOTES['likely_questions'] = ['A fresh question']
    try:
        state = client.post(_url(job) + 'run/', {'regenerate': True}, format='json').data
    finally:
        NOTES.update(NOTES_BEFORE)
    assert state['status'] == 'ready' and 'A fresh question' in state['note']['note']
    assert _prep_notes(job).get().pk == note.pk


def test_a_note_written_by_hand_blocks_the_run_and_survives_regenerate(client, owner, model, django_capture_on_commit_callbacks):
    job = _job(owner, 'applied')
    typed = ApplicationNote.objects.create(job=job, note='My own notes', note_type='interview_prep', created_by=owner)
    _move(client, job, 'interview', django_capture_on_commit_callbacks)
    assert model['prompts'] == []

    client.post(_url(job) + 'run/', {'regenerate': True}, format='json')
    typed.refresh_from_db()
    assert typed.note == 'My own notes' and _prep_notes(job).count() == 2


def test_no_posting_fails_before_any_paid_run(client, owner, model):
    job = _job(owner, 'interview', text='')
    state = client.post(_url(job) + 'run/', {}, format='json').data
    assert state['status'] == 'failed' and 'posting' in state['error']
    assert model['prompts'] == []


def test_a_run_a_crash_cut_off_shows_failed_and_is_not_replayed(client, owner, model, django_capture_on_commit_callbacks):
    job = _job(owner, 'applied')
    interview_prep._record(job, owner.pk, status='running', error='')
    _move(client, job, 'interview', django_capture_on_commit_callbacks)
    state = client.get(_url(job)).data
    assert (state['status'], state['error']) == ('failed', interview_prep.INTERRUPTED)
    assert model['prompts'] == []


def test_a_regenerated_note_is_the_one_shown_even_with_a_newer_note_typed_by_hand(client, owner, model):
    job = _job(owner, 'interview')
    client.post(_url(job) + 'run/', {}, format='json')
    ApplicationNote.objects.create(job=job, note='Typed later', note_type='interview_prep', created_by=owner)
    assert 'Likely questions' in client.post(_url(job) + 'run/', {'regenerate': True}, format='json').data['note']['note']
    assert _prep_notes(job).filter(note='Typed later').exists()


def test_a_job_that_left_interview_while_waiting_costs_nothing(client, owner, model, monkeypatch, django_capture_on_commit_callbacks):
    monkeypatch.setattr(interview_prep, 'Thread', HeldThread)
    job = _job(owner, 'applied')
    _move(client, job, 'interview', django_capture_on_commit_callbacks)
    _move(client, job, 'rejected', django_capture_on_commit_callbacks)
    HeldThread.held[0].target(*HeldThread.held[0].args)
    assert model['prompts'] == [] and not interview_prep._active


def test_without_models_nothing_starts_and_nothing_shows(client, owner, model, settings, django_capture_on_commit_callbacks):
    settings.CODEX_CV_ENABLED = False
    job = _job(owner, 'applied')
    _move(client, job, 'interview', django_capture_on_commit_callbacks)
    assert model['prompts'] == []
    assert client.get(_url(job)).status_code == 404
    assert client.post(_url(job) + 'run/', {}, format='json').status_code == 404


def test_another_account_cannot_reach_a_job(client, owner, model):
    stranger = User.objects.create_user('stranger', password='pw')
    job = _job(stranger, 'interview')
    assert client.get(_url(job)).status_code == 404
    assert client.post(_url(job) + 'run/', {}, format='json').status_code == 404
    assert model['prompts'] == []


def test_a_confirmed_mailbox_suggestion_starts_notes_too(owner, model, django_capture_on_commit_callbacks):
    job = _job(owner, 'applied')
    run = MailboxRun.objects.create()
    message = MailboxMessage.objects.create(run=run, uid=1, sender='hr@acme.test', subject='Interview', body_text='Come in', classification='interview_invitation', matched_job=job)
    suggestion = MailboxSuggestion.objects.create(message=message, job=job, suggestion_type='status_change', payload={'status': 'interview'})
    with django_capture_on_commit_callbacks(execute=True):
        mailbox.apply_suggestion(suggestion, user=owner)
    assert len(model['prompts']) == 1


# --- the queue, Pause and Stop -------------------------------------------------------------------

def test_a_run_shows_in_the_queue_and_an_idle_queue_reads_nothing_extra(client, owner, model, monkeypatch, django_capture_on_commit_callbacks):
    with CaptureQueriesContext(connection) as idle:
        assert interview_prep.queue_items(owner) == []
    assert len(idle) == 0

    monkeypatch.setattr(interview_prep, 'Thread', HeldThread)
    job = _job(owner, 'applied')
    _move(client, job, 'interview', django_capture_on_commit_callbacks)
    items = [item for item in application_prep.queue_state(owner)['items'] if item['key'] == interview_prep.QUEUE_KEY]
    assert [(item['job_id'], item['status'], item['label']) for item in items] == [(job.id, 'running', 'Waiting to write prep notes')]


def test_a_run_refused_at_the_queue_shows_failed_instead_of_queued_for_ever(client, owner, model, monkeypatch, tmp_path):
    monkeypatch.setenv('DACHAPPLY_CONTROL_DB', str(tmp_path / 'control.sqlite3'))
    monkeypatch.setattr(interview_prep._run, 'submit', lambda *args: None)  # its previous unit has not closed yet
    job = _job(owner, 'interview')
    state = client.post(_url(job) + 'run/', {}, format='json').data
    assert (state['status'], state['error']) == ('failed', interview_prep.NOT_STARTED)
    assert not interview_prep._active


@pytest.fixture
def control(tmp_path, monkeypatch):
    monkeypatch.setenv('DACHAPPLY_CONTROL_DB', str(tmp_path / 'control.sqlite3'))
    monkeypatch.setattr(processing_control.threading, 'Thread', HeldThread)
    return processing_control.store()


def test_pause_holds_the_run_and_resume_makes_exactly_one(client, owner, model, control, django_capture_on_commit_callbacks):
    control.mode('paused')
    job = _job(owner, 'applied')
    _move(client, job, 'interview', django_capture_on_commit_callbacks)

    target, (store, unit, kind, args, kwargs, limit) = HeldThread.held[0].target, HeldThread.held[0].args
    assert not control.claim(unit, kind, limit)
    assert model['prompts'] == []
    assert control.status()['remaining_jobs'] == 1  # the dashboard counts it as waiting
    assert store.enqueue(kind, {'args': args, 'kwargs': kwargs}) is None  # a second process is refused too

    control.mode('running')
    target(store, unit, kind, args, kwargs, limit)
    assert len(model['prompts']) == 1
    assert control.status()['completed_jobs'] == 1


def test_a_queued_run_recovered_after_a_restart_stays_owned_and_runs_once(client, owner, model, control, django_capture_on_commit_callbacks):
    job = _job(owner, 'applied')
    _move(client, job, 'interview', django_capture_on_commit_callbacks)
    interview_prep._active.clear()  # the process restarted
    HeldThread.held.clear()

    processing_control.recover_pending()
    assert job.id in interview_prep._active
    assert client.get(_url(job)).data['status'] == 'queued'
    HeldThread.held[0].target(*HeldThread.held[0].args)
    assert len(model['prompts']) == 1
