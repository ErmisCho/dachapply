"""TASK-351/352/353: the /api/stats/ lists behind Next up and the clear-skip action, the action
itself, and the funnel and fit bands that count every job that reached interview."""
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APIClient

from jobradar.models import REACHED_INTERVIEW, JobEvaluation, JobLead

CLEAR = '/api/jobs/clear-skip-recommended/'


@pytest.fixture
def owner(db):
    return User.objects.create_user('flow-owner', password='pw')


@pytest.fixture
def client(owner):
    c = APIClient()
    c.force_authenticate(owner)
    return c


def make(owner, status='new', recommendation=None, fit=50, **kwargs):
    kwargs.setdefault('company', 'Acme')
    kwargs.setdefault('title', 'Engineer')
    job = JobLead.objects.create(created_by=owner, status=status, **kwargs)
    if recommendation:
        JobEvaluation.objects.create(job=job, fit_score=fit, priority='low', recommendation=recommendation)
    return job


def stats(client):
    return client.get('/api/stats/').data


def test_selection_is_new_jobs_whose_latest_evaluation_says_skip(client, owner):
    target = make(owner, recommendation='skip', company='Target')
    make(owner, recommendation='apply')
    make(owner)  # never evaluated
    make(owner, status='reviewed', recommendation='skip')
    make(owner, status='to_apply', recommendation='skip')
    changed_mind = make(owner, recommendation='skip')
    JobEvaluation.objects.create(job=changed_mind, fit_score=90, priority='high', recommendation='apply')
    now_skip = make(owner, recommendation='apply', company='Now skip')
    JobEvaluation.objects.create(job=now_skip, fit_score=20, priority='low', recommendation='skip')

    rows = stats(client)['skip_recommended_new']

    assert rows == [{'id': now_skip.id, 'company': 'Now skip', 'title': 'Engineer'}, {'id': target.id, 'company': 'Target', 'title': 'Engineer'}]


def test_confirming_moves_exactly_the_confirmed_jobs(client, owner):
    confirmed = make(owner, recommendation='skip')
    arrived_after_the_list = make(owner, recommendation='skip')

    response = client.post(CLEAR, {'ids': [confirmed.id]}, format='json')

    assert response.status_code == 200 and response.data == {'moved': [confirmed.id]}
    confirmed.refresh_from_db()
    arrived_after_the_list.refresh_from_db()
    assert confirmed.status == 'skipped'
    assert arrived_after_the_list.status == 'new'


def test_a_job_that_changed_after_the_list_was_shown_stays_put(client, owner):
    promoted = make(owner, status='to_apply', recommendation='skip')
    reevaluated = make(owner, recommendation='skip')
    JobEvaluation.objects.create(job=reevaluated, fit_score=90, priority='high', recommendation='apply')

    response = client.post(CLEAR, {'ids': [promoted.id, reevaluated.id]}, format='json')

    assert response.data == {'moved': []}
    promoted.refresh_from_db()
    reevaluated.refresh_from_db()
    assert (promoted.status, reevaluated.status) == ('to_apply', 'new')


def test_another_users_job_cannot_be_moved(client):
    stranger = User.objects.create_user('flow-stranger', password='pw')
    theirs = make(stranger, recommendation='skip')
    handed_over = make(stranger, recommendation='skip', submitted_for=User.objects.create_user('flow-friend', password='pw'))

    response = client.post(CLEAR, {'ids': [theirs.id, handed_over.id]}, format='json')

    assert response.data == {'moved': []}
    theirs.refresh_from_db()
    handed_over.refresh_from_db()
    assert theirs.status == handed_over.status == 'new'
    assert stats(client)['skip_recommended_new'] == []


@pytest.mark.parametrize('body', [{}, {'ids': 'all'}, {'ids': ['1']}, {'ids': [True]}, {'ids': None}])
def test_ids_must_be_a_list_of_integers(client, owner, body):
    job = make(owner, recommendation='skip')
    assert client.post(CLEAR, body, format='json').status_code == 400
    job.refresh_from_db()
    assert job.status == 'new'


def test_clearing_needs_a_logged_in_user(owner):
    job = make(owner, recommendation='skip')
    assert APIClient().post(CLEAR, {'ids': [job.id]}, format='json').status_code in (401, 403)
    job.refresh_from_db()
    assert job.status == 'new'


def test_clearing_starts_no_generation_or_model_call(client, owner, django_capture_on_commit_callbacks):
    job = make(owner, recommendation='skip')
    with patch('jobradar.services.application_prep.prepare_on_to_apply') as prepare, \
            patch('jobradar.services.application_prep.start_pipeline') as pipeline, \
            patch('jobradar.services.application_prep.reanalyse_changed') as reanalyse, \
            patch('jobradar.services.cv_generator.delete_generated_metadata') as delete_metadata, \
            django_capture_on_commit_callbacks(execute=True) as callbacks:
        assert client.post(CLEAR, {'ids': [job.id]}, format='json').data == {'moved': [job.id]}
    assert callbacks == []
    prepare.assert_not_called()
    pipeline.assert_not_called()
    reanalyse.assert_not_called()
    delete_metadata.assert_not_called()


def test_a_cleared_job_has_what_a_board_patch_gives_it(client, owner):
    cleared = make(owner, recommendation='skip', feedback_due_date=timezone.localdate())
    patched = make(owner, recommendation='skip', feedback_due_date=timezone.localdate())
    client.post(CLEAR, {'ids': [cleared.id]}, format='json')
    client.patch(f'/api/jobs/{patched.id}/', {'status': 'skipped'}, format='json')
    fields = ('status', 'status_date', 'last_update_date', 'feedback_due_date', 'interview_stage', 'applied_at')
    assert JobLead.objects.filter(pk=cleared.id).values(*fields).get() == JobLead.objects.filter(pk=patched.id).values(*fields).get()


def test_next_up_leads_with_ready_to_submit_and_leaves_out_skips(client, owner):
    make(owner, status='new', recommendation='apply', fit=99, company='New apply')
    make(owner, status='new', recommendation='skip', fit=98, company='New skip')
    make(owner, status='new', company='New unanalysed')
    make(owner, status='to_apply', recommendation='apply', fit=90, company='To apply')
    make(owner, status='ready_to_submit', recommendation='maybe', fit=70, company='Ready low')
    make(owner, status='ready_to_submit', recommendation='apply', fit=80, company='Ready high')
    make(owner, status='applied', recommendation='apply', fit=97, company='Applied')

    data = stats(client)

    assert [row['company'] for row in data['next_up']] == ['Ready high', 'Ready low', 'To apply', 'New apply']
    assert data['next_up_total'] == 4
    assert data['next_up'][0]['latest_fit_score'] == 80


def test_next_up_is_compact_but_reports_the_total(client, owner):
    for _ in range(8):
        make(owner, status='ready_to_submit')
    data = stats(client)
    assert len(data['next_up']) == 6
    assert data['next_up_total'] == 8


def test_funnel_counts_every_job_that_reached_interview(client, owner):
    today = timezone.localdate()
    make(owner, status='applied', applied_at=today)
    make(owner, status='interview', applied_at=today)
    make(owner, status='interview')
    make(owner, status='offer')
    make(owner, status='rejected', interview_at=timezone.now())

    funnel = stats(client)['funnel']

    reached = JobLead.objects.filter(REACHED_INTERVIEW).count()
    assert reached == 4
    assert funnel['all_time']['interviews'] == reached
    assert funnel['all_time']['applications'] == 5
    assert funnel['all_time']['offers'] == 1
    assert funnel['all_time']['applied_to_interview_rate'] == 80.0
    assert funnel['interviews_without_application'] == 3


def test_recent_funnel_dates_an_undated_interview_by_its_status_date(client, owner):
    today = timezone.localdate()
    make(owner, status='interview', status_date=today)
    make(owner, status='interview', status_date=today - timedelta(days=200))
    funnel = stats(client)['funnel']
    assert funnel['recent']['interviews'] == 1
    assert funnel['all_time']['interviews'] == 2


def test_undated_interviews_stay_out_of_the_application_pace(client, owner):
    make(owner, status='interview')
    data = stats(client)
    assert data['applications_sent'] == 0
    assert data['applications_this_week'] == 0


def test_fit_bands_use_the_latest_evaluation_and_cover_every_application(client, owner):
    today = timezone.localdate()
    for fit, status in ((80, 'interview'), (100, 'rejected'), (79, 'applied'), (70, 'rejected'), (69, 'applied'), (60, 'applied'), (59, 'rejected'), (0, 'applied')):
        make(owner, status=status, applied_at=today, recommendation='apply', fit=fit)
    make(owner, status='applied', applied_at=today)
    make(owner, status='interview')  # no application date, no score
    rescored = make(owner, status='applied', applied_at=today, recommendation='apply', fit=90)
    JobEvaluation.objects.create(job=rescored, fit_score=65, priority='low', recommendation='maybe')
    make(owner, status='new', recommendation='apply', fit=95)  # never applied to

    funnel = stats(client)['funnel']

    assert funnel['fit_bands'] == [
        {'band': '80+', 'applications': 2, 'interviews': 1, 'rejections': 1},
        {'band': '70-79', 'applications': 2, 'interviews': 0, 'rejections': 1},
        {'band': '60-69', 'applications': 3, 'interviews': 0, 'rejections': 0},
        {'band': 'Under 60', 'applications': 2, 'interviews': 0, 'rejections': 1},
        {'band': 'No score', 'applications': 2, 'interviews': 1, 'rejections': 0},
    ]
    assert sum(band['applications'] for band in funnel['fit_bands']) == funnel['all_time']['applications']


def test_waiting_counts_applications_with_no_outcome_yet(client, owner):
    today = timezone.localdate()
    make(owner, status='applied', applied_at=today)
    make(owner, status='applied', applied_at=today)
    make(owner, status='applied', applied_at=today, interview_at=timezone.now())
    make(owner, status='interview', applied_at=today)
    make(owner, status='rejected', applied_at=today)
    make(owner, status='withdrawn', applied_at=today)
    assert stats(client)['funnel']['all_time']['waiting'] == 2


def test_stats_stay_scoped_to_the_requesting_user(client):
    stranger = User.objects.create_user('flow-other', password='pw')
    make(stranger, status='interview')
    make(stranger, status='ready_to_submit')
    data = stats(client)
    assert data['funnel']['all_time']['interviews'] == 0
    assert data['next_up'] == []
