"""TASK-335/336/337: existing open jobs go through the pipeline too, within the Profile's daily budgets --
waiting jobs analysed, apply/maybe jobs with nothing prepared get documents, a posting the automatic refresh
replaced and an evaluation older than N days are analysed again, and documents follow the review rule.

Hermetic like test_auto_pipeline: the fetch and the evaluator's model runner are replaced, and every worker
runs in-thread (SyncThread), inside this test's transaction.
"""
from datetime import timedelta
from pathlib import Path

import pytest
from django.utils import timezone

from jobradar.models import JobEvaluation, JobLead, UserProfile
from jobradar.services import application_prep, mailbox, mailbox_loop
from jobradar.services.cv_generator import _record_artifact_metadata
from jobradar.services.posting_fetch import _source_hash
from jobradar.tests.test_application_prep import POSTING, _req, client, generator, owner, workspace  # noqa: F401 -- fixtures
from jobradar.tests.test_application_prep_queue import _at, tasks  # noqa: F401 -- fixtures
from jobradar.tests.test_auto_pipeline import model  # noqa: F401 -- fixture
from jobradar.tests.test_link_only_prep import SUBSTANTIAL, THIN, fetch  # noqa: F401 -- fixtures

NOW = '2026-10-22T09:00:00+02:00'
CHOICE = {'provider': 'openai', 'model': 'gpt-6.1', 'effort': 'high', 'speed': 'normal'}


@pytest.fixture
def today(monkeypatch):
    _at(monkeypatch, NOW)


def _job(owner, n, status='new', url=True, text=POSTING, age_hours=0):
    job = JobLead.objects.create(company='ACME', title=f'Role {n}', status=status, created_by=owner, original_source_text=text,
                                 url=f'https://jobs.example.test/{n}' if url else '', application_requirements=_req('de'))
    JobLead.objects.filter(pk=job.pk).update(created_at=timezone.now() - timedelta(hours=age_hours))
    return job


def _evaluated(owner, n, recommendation='apply', fit=70, priority='high', days=0, **job):
    job = _job(owner, n, **job)
    evaluation = JobEvaluation.objects.create(job=job, fit_score=fit, priority=priority, recommendation=recommendation, summary='')
    JobEvaluation.objects.filter(pk=evaluation.pk).update(created_at=timezone.now() - timedelta(days=days))
    return job


def _limits(owner, analyse=10, prepare=0, days=0):
    UserProfile.objects.filter(user=owner).update(daily_analyse_limit=analyse, daily_prepare_limit=prepare, reanalyse_after_days=days)


def _run(owner, capture):
    with capture(execute=True):
        application_prep.run_daily(owner)


def _analysed(model):
    return [ids[0] for ids, commit in model['calls'] if commit]


# --- TASK-335: waiting jobs ----------------------------------------------------------------------

@pytest.mark.parametrize('limit, count', [(0, 0), (2, 2), (None, 3)])
def test_waiting_jobs_are_analysed_newest_first_up_to_the_limit_once_a_day(owner, tasks, fetch, model, today, monkeypatch, django_capture_on_commit_callbacks, limit, count):
    _limits(owner, analyse=limit)
    oldest, middle, newest = (_job(owner, n, age_hours=hours) for n, hours in ((1, 30), (2, 20), (3, 10)))
    _job(owner, 'no-link', url=False); _job(owner, 'applied', status='applied'); _evaluated(owner, 'done')  # never waiting
    model['answers'] = ['skip'] * 3
    _run(owner, django_capture_on_commit_callbacks)
    assert _analysed(model) == [newest.id, middle.id, oldest.id][:count]
    _run(owner, django_capture_on_commit_callbacks)  # later the same day: today's budget is spent
    assert len(model['calls']) == count
    if limit == 2:
        _at(monkeypatch, '2026-10-23T09:00:00+02:00')  # the next day, the rest
        _run(owner, django_capture_on_commit_callbacks)
        assert _analysed(model) == [newest.id, middle.id, oldest.id]


def test_a_failed_waiting_job_is_tried_again_the_next_day_not_on_every_tick(owner, tasks, fetch, model, today, monkeypatch, django_capture_on_commit_callbacks):
    _limits(owner, analyse=None)
    job = _job(owner, 1)
    model['answers'] = [RuntimeError('provider down'), 'skip']
    _run(owner, django_capture_on_commit_callbacks)
    _run(owner, django_capture_on_commit_callbacks)
    assert _analysed(model) == [job.id] and application_prep._state(job, owner)['pipeline']['stage'] == 'failed'
    _at(monkeypatch, '2026-10-23T09:00:00+02:00')
    _run(owner, django_capture_on_commit_callbacks)
    assert _analysed(model) == [job.id, job.id] and application_prep._state(job, owner)['pipeline']['stage'] == 'skipped'


def test_the_local_loop_tick_spends_the_daily_budget(owner, tasks, fetch, model, today, monkeypatch, django_capture_on_commit_callbacks):
    _limits(owner, analyse=1)
    monkeypatch.setattr(mailbox, 'run_check', lambda force=False: None)
    job = _job(owner, 1)
    model['answers'] = ['skip']
    with django_capture_on_commit_callbacks(execute=True):
        mailbox_loop.tick()
    assert _analysed(model) == [job.id]


# --- TASK-335: documents for apply/maybe jobs with nothing prepared ------------------------------

@pytest.mark.parametrize('limit, count', [(0, 0), (2, 2), (None, 3)])
def test_documents_go_to_the_best_unprepared_jobs_up_to_the_limit_once_a_day(owner, tasks, fetch, model, today, settings, workspace, django_capture_on_commit_callbacks, limit, count):
    settings.PREP_QUEUE_CONCURRENCY = 10  # every queued variant starts, so the start order is the batch order
    _limits(owner, analyse=0, prepare=limit)
    low = _evaluated(owner, 1, fit=60, status='to_apply')
    best = _evaluated(owner, 2, recommendation='maybe', fit=90, priority='low', status='reviewed')
    second = _evaluated(owner, 3, fit=90, priority='medium')
    _evaluated(owner, 'skip', recommendation='skip', fit=95)
    _evaluated(owner, 'applied', fit=95, status='applied')
    refused = _evaluated(owner, 'refused', fit=95)
    application_prep._save(refused, owner.pk, lambda prep: prep.update(reason='The job has no usable posting text yet.'))
    owned = _evaluated(owner, 'owned', fit=95)
    tex = Path(workspace) / 'CVs' / 'Owner-CV.tex'
    tex.write_text('owner cv', encoding='utf-8')
    _record_artifact_metadata(owned, owner.pk, {'cv_tex': str(tex)})
    _run(owner, django_capture_on_commit_callbacks)
    assert tasks['started'] == [(job.id, 'cv-de') for job in (second, best, low)][:count]
    _run(owner, django_capture_on_commit_callbacks)  # the same day again: nothing more
    assert len(tasks['started']) == count
    assert model['calls'] == []


# --- TASK-336: a posting the automatic refresh replaced ------------------------------------------

def _refresh(client, capture):
    with capture(execute=True):
        assert client.post('/api/jobs/source-text/refresh-due/').status_code == 200


def test_changed_text_is_reanalysed_and_committed_unchanged_text_is_not(owner, client, tasks, fetch, model, today, django_capture_on_commit_callbacks):
    _limits(owner, analyse=1)
    changed = _evaluated(owner, 'changed', text=THIN, status='to_apply')
    _evaluated(owner, 'same', text=POSTING, status='to_apply')  # the fetch returns POSTING: identical
    model['answers'] = ['apply']
    _refresh(client, django_capture_on_commit_callbacks)
    assert model['calls'] == [([changed.id], True)] and JobEvaluation.objects.filter(job=changed).count() == 2
    assert tasks['started'] == [(changed.id, 'cv-de')]  # nothing was prepared yet, so the evaluation hook prepares


def test_a_change_over_the_budget_waits_and_the_daily_run_takes_it_first(owner, client, tasks, fetch, model, today, monkeypatch, django_capture_on_commit_callbacks):
    _limits(owner, analyse=0)
    changed = _evaluated(owner, 'changed', text=THIN, status='new')
    _refresh(client, django_capture_on_commit_callbacks)
    assert model['calls'] == [] and application_prep._state(changed, owner)['posting_changed'] is True
    waiting = _job(owner, 'waiting')
    _limits(owner, analyse=1)
    model['answers'] = ['skip']
    _run(owner, django_capture_on_commit_callbacks)
    assert _analysed(model) == [changed.id] and 'posting_changed' not in application_prep._state(changed, owner)
    _at(monkeypatch, '2026-10-23T09:00:00+02:00')
    model['answers'] = ['skip']
    _run(owner, django_capture_on_commit_callbacks)
    assert _analysed(model) == [changed.id, waiting.id]


def _variant(key, status='ready', review=None, files=None):
    document, language = key.split('-')
    variant = {'document': document, 'language': language, 'letter_template': '', 'status': status, 'task_id': '', 'error': '',
               'files': files or {}, 'queued_at': '2026-10-01T08:00:00+00:00', 'started_at': None, 'finished_at': None}
    return {**variant, 'review': review} if review else variant


def _prepared(owner, workspace, variants, n='prepared', text=THIN, **evaluation):
    job = _evaluated(owner, n, text=text, status='to_apply', **evaluation)
    files = {}
    for key in variants:
        tex = Path(workspace) / 'CVs' / f'{n}-{key}.tex'
        tex.write_text(key, encoding='utf-8'); tex.with_suffix('.pdf').write_bytes(b'%PDF')
        files[key] = {'cv_tex': str(tex), 'cv_pdf': str(tex.with_suffix('.pdf'))}
    application_prep._save(job, owner.pk, lambda prep: prep.update(model=CHOICE, variants={
        key: _variant(key, status, review, files[key] if status == 'ready' else None) for key, (status, review) in variants.items()}))
    return job, files


def test_unreviewed_documents_are_redone_and_reviewed_ones_stay_with_a_note(owner, client, tasks, fetch, model, today, settings, workspace, django_capture_on_commit_callbacks):
    settings.PREP_QUEUE_CONCURRENCY = 10
    job, files = _prepared(owner, workspace, {'cv-de': ('ready', None), 'cv-en': ('ready', 'keep'), 'letter-de': ('ready', 'discard'), 'letter-en': ('failed', None)})
    model['answers'] = ['maybe']
    _refresh(client, django_capture_on_commit_callbacks)
    assert model['calls'] == [([job.id], True)]
    assert tasks['started'] == [(job.id, 'cv-de'), (job.id, 'letter-en')]
    variants = application_prep._state(job, owner)['variants']
    assert variants['cv-de']['status'] == variants['letter-en']['status'] == 'running'
    assert variants['cv-en']['files'] == files['cv-en'] and variants['letter-de']['files'] == files['letter-de']
    assert all(Path(path).is_file() for paths in files.values() for path in paths.values())  # nothing deleted
    state = application_prep.public_state(job, owner)
    assert state['outdated'] == application_prep.CHANGED == 'Posting changed since these documents were made'
    application_prep.review(job, owner, 'keep', key='cv-en')  # the owner looked again
    assert application_prep.public_state(job, owner)['outdated'] == ''


def test_only_unreviewed_documents_are_redone_without_a_note(owner, client, tasks, fetch, model, today, workspace, django_capture_on_commit_callbacks):
    job, _ = _prepared(owner, workspace, {'cv-de': ('ready', None)})
    model['answers'] = ['apply']
    _refresh(client, django_capture_on_commit_callbacks)
    assert tasks['started'] == [(job.id, 'cv-de')] and application_prep.public_state(job, owner)['outdated'] == ''


def test_a_skip_after_the_change_stops_document_work_and_keeps_files(owner, client, tasks, fetch, model, today, workspace, django_capture_on_commit_callbacks):
    job, files = _prepared(owner, workspace, {'cv-de': ('ready', None), 'cv-en': ('queued', None)})
    application_prep._queue.append((job.id, owner.pk, 'cv-en'))
    model['answers'] = ['skip']
    _refresh(client, django_capture_on_commit_callbacks)
    variants = application_prep._state(job, owner)['variants']
    assert tasks['started'] == [] and application_prep._queue == []
    assert (variants['cv-de']['status'], variants['cv-de']['files']) == ('ready', files['cv-de']) and variants['cv-en']['status'] == 'cancelled'
    assert all(Path(path).is_file() for path in files['cv-de'].values())


# --- TASK-338: changed ads of New/Reviewed jobs, Use fetched, and redo only if something changed ------

CHANGED_AD = SUBSTANTIAL + ' Update: the team now works remotely.'


@pytest.mark.parametrize('status', ['new', 'reviewed'])
def test_a_changed_full_posting_of_a_new_or_reviewed_job_is_accepted_and_reanalysed(owner, client, tasks, fetch, model, today, django_capture_on_commit_callbacks, status):
    job = _evaluated(owner, 'changed', text=SUBSTANTIAL, status=status)
    fetch['result'] = {'ok': True, 'text': CHANGED_AD, 'error': '', 'final_url': ''}
    model['answers'] = ['skip']
    _refresh(client, django_capture_on_commit_callbacks)
    job.refresh_from_db()
    assert job.original_source_text == CHANGED_AD and job.pending_source_text == '' and job.status == status
    assert model['calls'] == [([job.id], True)]


def test_a_dismissed_copy_stays_dismissed(owner, client, tasks, fetch, model, today, django_capture_on_commit_callbacks):
    job = _evaluated(owner, 'dismissed', text=SUBSTANTIAL)
    JobLead.objects.filter(pk=job.pk).update(dismissed_source_hash=_source_hash(CHANGED_AD))
    fetch['result'] = {'ok': True, 'text': CHANGED_AD, 'error': '', 'final_url': ''}
    _refresh(client, django_capture_on_commit_callbacks)
    job.refresh_from_db()
    assert job.original_source_text == SUBSTANTIAL and job.pending_source_text == '' and model['calls'] == []


def test_a_to_apply_change_is_staged_and_use_fetched_reanalyses(owner, client, tasks, fetch, model, today, django_capture_on_commit_callbacks):
    job = _evaluated(owner, 'staged', text=SUBSTANTIAL, status='to_apply')
    fetch['result'] = {'ok': True, 'text': CHANGED_AD, 'error': '', 'final_url': ''}
    _refresh(client, django_capture_on_commit_callbacks)
    job.refresh_from_db()
    assert job.pending_source_text == CHANGED_AD and job.original_source_text == SUBSTANTIAL and model['calls'] == []
    model['answers'] = ['apply']
    with django_capture_on_commit_callbacks(execute=True):
        assert client.patch(f'/api/jobs/{job.id}/source-text/', {'original_source_text': CHANGED_AD}, format='json').status_code == 200
    assert model['calls'] == [([job.id], True)] and tasks['started'] == [(job.id, 'cv-de')]
    with django_capture_on_commit_callbacks(execute=True):  # Keep current with the same text: nothing to analyse
        assert client.patch(f'/api/jobs/{job.id}/source-text/', {'original_source_text': CHANGED_AD}, format='json').status_code == 200
    assert len(model['calls']) == 1


def test_a_stale_recheck_with_the_same_outcome_leaves_documents_alone(owner, tasks, fetch, model, today, workspace, django_capture_on_commit_callbacks):
    _limits(owner, analyse=1, prepare=10, days=7)
    job, files = _prepared(owner, workspace, {'cv-de': ('ready', None), 'cv-en': ('ready', 'keep')}, text=SUBSTANTIAL, days=10)
    model['answers'] = ['apply']  # as before
    _run(owner, django_capture_on_commit_callbacks)
    variants = application_prep._state(job, owner)['variants']
    assert model['calls'] == [([job.id], True)] and tasks['started'] == []
    assert variants['cv-de']['files'] == files['cv-de'] and application_prep.public_state(job, owner)['outdated'] == ''


def test_a_changed_verdict_redoes_unreviewed_documents_with_a_note(owner, tasks, fetch, model, today, workspace, django_capture_on_commit_callbacks):
    _limits(owner, analyse=1, prepare=10, days=7)
    job, _ = _prepared(owner, workspace, {'cv-de': ('ready', None), 'cv-en': ('ready', 'keep')}, text=SUBSTANTIAL, days=10, recommendation='maybe')
    model['answers'] = ['apply']
    _run(owner, django_capture_on_commit_callbacks)
    assert tasks['started'] == [(job.id, 'cv-de')]
    assert application_prep.public_state(job, owner)['outdated'] == application_prep.REANALYSED


@pytest.mark.parametrize('cap, redone', [(0, 0), (1, 1)])
def test_redone_documents_count_against_the_prepare_cap_and_wait_for_the_next_day(owner, tasks, fetch, model, today, settings, monkeypatch, workspace, django_capture_on_commit_callbacks, cap, redone):
    settings.PREP_QUEUE_CONCURRENCY = 10
    _limits(owner, analyse=2, prepare=cap, days=7)
    first, _ = _prepared(owner, workspace, {'cv-de': ('ready', None)}, n='first', text=SUBSTANTIAL, days=10, recommendation='maybe')
    second, _ = _prepared(owner, workspace, {'cv-de': ('ready', None)}, n='second', text=SUBSTANTIAL, days=9, recommendation='maybe')
    model['answers'] = ['apply', 'apply']
    _run(owner, django_capture_on_commit_callbacks)
    assert tasks['started'] == [(first.id, 'cv-de')][:redone]
    waiting = [job for job in (first, second) if application_prep._state(job, owner).get('redo_pending')]
    assert waiting == [first, second][redone:]
    _limits(owner, analyse=0, prepare=2, days=7)
    _at(monkeypatch, '2026-10-23T09:00:00+02:00')
    _run(owner, django_capture_on_commit_callbacks)  # the next day's batch redoes the waiting ones first
    assert sorted(job_id for job_id, _ in tasks['started']) == [first.id, second.id]


# --- TASK-337: analyses older than N days ---------------------------------------------------------

def test_evaluations_older_than_n_days_are_reanalysed_oldest_first(owner, tasks, fetch, model, today, django_capture_on_commit_callbacks):
    _limits(owner, analyse=None, days=7)
    older, old = _evaluated(owner, 'older', recommendation='skip', days=10), _evaluated(owner, 'old', recommendation='skip', days=8)
    _evaluated(owner, 'recent', recommendation='skip', days=3)
    _evaluated(owner, 'closed', recommendation='skip', days=30, status='archived')
    model['answers'] = ['skip', 'skip']
    _run(owner, django_capture_on_commit_callbacks)
    assert _analysed(model) == [older.id, old.id]
    _run(owner, django_capture_on_commit_callbacks)  # now fresh: nothing again
    assert len(model['calls']) == 2


def test_off_reanalyses_nothing(owner, tasks, fetch, model, today, django_capture_on_commit_callbacks):
    _limits(owner, analyse=None, days=0)
    _evaluated(owner, 'older', days=60)
    _run(owner, django_capture_on_commit_callbacks)
    assert model['calls'] == []


def test_stale_and_waiting_jobs_share_the_daily_analysis_cap(owner, tasks, fetch, model, today, django_capture_on_commit_callbacks):
    _limits(owner, analyse=2, days=7)
    older, _ = _evaluated(owner, 'older', recommendation='skip', days=10), _evaluated(owner, 'old', recommendation='skip', days=8)
    waiting = _job(owner, 'waiting')
    model['answers'] = ['skip', 'skip']
    _run(owner, django_capture_on_commit_callbacks)
    assert _analysed(model) == [waiting.id, older.id]


# --- the Profile fields ---------------------------------------------------------------------------

def test_profile_round_trip_of_the_daily_sliders(owner, client):
    data = client.get('/api/profile/').data
    assert (data['daily_analyse_limit'], data['daily_prepare_limit'], data['reanalyse_after_days']) == (10, 10, 7)
    saved = client.patch('/api/profile/', {'daily_analyse_limit': None, 'daily_prepare_limit': 0, 'reanalyse_after_days': 0}, format='json').data
    assert (saved['daily_analyse_limit'], saved['daily_prepare_limit'], saved['reanalyse_after_days']) == (None, 0, 0)
    profile = UserProfile.objects.get(user=owner)
    assert (profile.daily_analyse_limit, profile.daily_prepare_limit, profile.reanalyse_after_days) == (None, 0, 0)
    assert client.get('/api/profile/').data['daily_analyse_limit'] is None  # Unlimited, never read back as unset
    assert client.patch('/api/profile/', {'daily_analyse_limit': 50, 'reanalyse_after_days': 60}, format='json').status_code == 200
    for field, value in (('daily_analyse_limit', 51), ('daily_prepare_limit', -1), ('daily_prepare_limit', 'many'),
                         ('reanalyse_after_days', 61), ('reanalyse_after_days', None)):
        assert client.patch('/api/profile/', {field: value}, format='json').status_code == 400, (field, value)
    profile.refresh_from_db()
    assert (profile.daily_analyse_limit, profile.daily_prepare_limit, profile.reanalyse_after_days) == (50, 0, 60)
