"""TASK-284: a job with evaluations of different priorities/fit scores must stay ONE row --
priority_rank and the fit sort read the latest evaluation only (what the board shows)."""
from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APIClient

from jobradar.models import JobEvaluation, JobLead


@pytest.fixture
def client(db):
    c = APIClient(); c.user = User.objects.create_user('t284', password='pw'); c.force_authenticate(c.user); return c


def _evaluate(job, fit_score, priority, age_days):
    ev = JobEvaluation.objects.create(job=job, fit_score=fit_score, priority=priority, recommendation='apply')
    JobEvaluation.objects.filter(pk=ev.pk).update(created_at=timezone.now() - timedelta(days=age_days))


@pytest.fixture
def jobs(client):
    flipped = JobLead.objects.create(company='Flipped', title='role', created_by=client.user)
    _evaluate(flipped, 90, 'high', age_days=2)   # older
    _evaluate(flipped, 40, 'low', age_days=1)    # latest -> rank 2, fit 40
    steady = JobLead.objects.create(company='Steady', title='role', created_by=client.user)
    _evaluate(steady, 60, 'medium', age_days=1)
    return flipped, steady


def test_detail_returns_200(client, jobs):
    assert client.get(f'/api/jobs/{jobs[0].pk}/').status_code == 200


@pytest.mark.parametrize('ordering', [None, 'recommended', 'priority', '-priority', 'fit_score', '-fit_score'])
def test_board_lists_the_job_once(client, jobs, ordering):
    r = client.get('/api/jobs/', {'ordering': ordering} if ordering else {})
    assert r.status_code == 200
    assert sorted(j['company'] for j in r.data) == ['Flipped', 'Steady']


def test_priority_and_fit_sorts_use_the_latest_evaluation(client, jobs):
    # Latest: Flipped low/40, Steady medium/60. Any older evaluation leaking in would put Flipped first.
    assert [j['company'] for j in client.get('/api/jobs/', {'ordering': 'priority'}).data] == ['Steady', 'Flipped']
    assert [j['company'] for j in client.get('/api/jobs/', {'ordering': '-fit_score'}).data] == ['Steady', 'Flipped']
