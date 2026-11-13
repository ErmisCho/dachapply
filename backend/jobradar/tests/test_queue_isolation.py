"""TASK-377: blocked and stalled analyses never hold other jobs in the queue."""
import time

import pytest

from jobradar.models import JobLead
from jobradar.services import application_prep, job_evaluator
from jobradar.tests.test_application_prep import POSTING, _req, client, generator, owner, workspace  # noqa: F401
from jobradar.tests.test_application_prep_queue import _evaluate, _items, _variant, tasks, timers  # noqa: F401
from jobradar.tests.test_analysis_lanes import _jobs, _join_pipelines, _profile, _until, lanes  # noqa: F401
from jobradar.tests.test_link_only_prep import fetch  # noqa: F401


@pytest.fixture
def isolated_lanes(tasks, lanes):  # TASK-377: install the document fake before the real pipeline threads.
    return lanes


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize('blocked_by', ['pending_source_text', 'missing_posting', 'failed_analysis'])
def test_blocked_job_does_not_hold_other_analyses_or_documents(owner, client, isolated_lanes, tasks, timers,
                                                            monkeypatch, django_capture_on_commit_callbacks, blocked_by):
    # TASK-377: keep one blocked row visible while two other jobs traverse analysis and the document queue.
    _profile(owner, analysis_concurrency=1)
    blocked, *others = _jobs(owner, 3)
    JobLead.objects.filter(pk__in=[blocked.id, *(job.id for job in others)]).update(application_requirements=_req('de'))
    evaluate = job_evaluator.evaluate_jobs

    def analyse(job_ids, user, *args, **kwargs):
        if job_ids == [blocked.id]:
            return {'ok': False, 'errors': ['canned analysis failure']}
        result = evaluate(job_ids, user, *args, **kwargs)
        _evaluate(JobLead.objects.get(pk=job_ids[0]), user, 'apply', django_capture_on_commit_callbacks)
        return {**result, 'preview': [{'recommendation': 'apply', 'fit_score': 80}]}
    monkeypatch.setattr(job_evaluator, 'evaluate_jobs', analyse)
    if blocked_by == 'failed_analysis':
        assert application_prep._pipeline(blocked.id, owner.pk) is False
        reason = 'Analysis failed: canned analysis failure. Press Retry.'
    else:
        fields = {'pending_source_text': POSTING + ' Alternative.'} if blocked_by == 'pending_source_text' else {'original_source_text': ''}
        JobLead.objects.filter(pk=blocked.id).update(**fields)
        application_prep.prepare(blocked.id, owner)
        reason = application_prep.CHOOSE_SOURCE if blocked_by == 'pending_source_text' else 'The job has no usable posting text yet.'
    assert application_prep._state(blocked, owner)['reason'] == reason
    assert tasks['started'] == []

    for job in others:
        isolated_lanes['gate'](job.id).set()
        assert application_prep._pipeline(job.id, owner.pk) is True
    assert isolated_lanes['entered'] == [job.id for job in others]
    assert tasks['started'] == [(others[0].id, 'cv-de')]
    tasks['end']('task-1')
    assert tasks['started'] == [(job.id, 'cv-de') for job in others]
    tasks['end']('task-2')
    assert all(_variant(job, owner, 'cv-de')['status'] == 'ready' for job in others)
    assert all(application_prep._state(job, owner)['pipeline']['stage'] == 'analysed' for job in others)
    assert application_prep._state(blocked, owner)['reason'] == reason
    assert next(item for item in _items(client) if item['job_id'] == blocked.id)['status'] in ('blocked', 'failed')


@pytest.mark.django_db(transaction=True)
@pytest.mark.django_db(transaction=True)
@pytest.mark.django_db
def test_provider_limit_pause_is_aggregated_and_expires(owner, workspace, timers):
    # TASK-377: multiple usage-limited rows produce one account notice; transient retries do not.
    from datetime import timedelta
    from django.utils import timezone
    jobs = _jobs(owner, 2)
    reset = timezone.now() + timedelta(minutes=10)
    for job in jobs:
        def fail(prep):
            retry = application_prep._retry_at(True, reset, prep)
            prep.update(reason='Provider usage limit', retry_at=retry)
        application_prep._save(job, owner.pk, fail)
    for job in jobs:  # TASK-377: an ordinary retry must not imply an account-wide provider pause.
        application_prep._save(job, owner.pk, lambda prep: prep.update(usage_limit=False))
    assert application_prep.queue_state(owner)['paused'] is None
    for job in jobs:
        application_prep._save(job, owner.pk, lambda prep: prep.update(usage_limit=True))
    paused = application_prep.queue_state(owner)['paused']
    assert paused == {'reason': 'provider_limit', 'resume_at': (reset + timedelta(minutes=1)).isoformat()}
    for job in jobs:
        application_prep._save(job, owner.pk, lambda prep: prep.update(retry_at=(timezone.now()-timedelta(seconds=1)).isoformat()))
    assert application_prep.queue_state(owner)['paused'] is None
