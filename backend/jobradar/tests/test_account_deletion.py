"""TASK-103: delete_account must follow access.owned_by, not created_by|submitted_for.

The old predicate treated "created it" as "owns it", so a friend who only submitted a job for
someone else (submitted_for=recipient) took the recipient's job -- and the recipient's
evaluations, notes and follow-ups via the job__in=owned_jobs cascades -- with them when they
deleted their own account. access.owned_by says a job belongs to the person it was submitted
*for*, so the deleting user's own jobs must go and a job they only handed off must not.
"""
import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from jobradar.models import ApplicationNote, FollowUp, JobEvaluation, JobLead
from jobradar.services import access


@pytest.fixture
def submitter(db):
    return User.objects.create_user('submitter', password='pw')


@pytest.fixture
def recipient(db):
    return User.objects.create_user('recipient', password='pw')


@pytest.fixture
def submitter_client(submitter):
    c = APIClient()
    c.force_authenticate(submitter)
    return c


def _evaluation(job):
    return JobEvaluation.objects.create(job=job, fit_score=80, priority='high', recommendation='apply')


def _followup(job):
    from django.utils import timezone
    return FollowUp.objects.create(job=job, follow_up_date=timezone.localdate(), reason='ping recruiter')


# AC2 -- the deleting user's own data is fully removed.

def test_own_job_and_its_evaluation_note_followup_are_deleted(submitter, submitter_client):
    job = JobLead.objects.create(company='Own Co', title='Own Role', created_by=submitter)
    _evaluation(job)
    ApplicationNote.objects.create(job=job, note='mine', created_by=submitter)
    _followup(job)

    r = submitter_client.delete('/api/auth/account/', {'password': 'pw'}, format='json')

    assert r.status_code == 200, r.data
    assert not JobLead.objects.filter(pk=job.pk).exists()
    assert not JobEvaluation.objects.filter(job_id=job.pk).exists()
    assert not ApplicationNote.objects.filter(job_id=job.pk).exists()
    assert not FollowUp.objects.filter(job_id=job.pk).exists()
    assert not User.objects.filter(username='submitter').exists()


# AC1 / AC3 -- a job handed off to someone else survives, with the recipient's data intact and
# the recipient's own read access unchanged (the cross-agent tripwire: accessible_jobs(recipient)
# must still return the job through the same rule TASK-84 pinned).

def test_job_submitted_for_someone_else_survives_with_recipient_data_intact(submitter, recipient, submitter_client):
    handed_off = JobLead.objects.create(company='Friend Co', title='Referral', created_by=submitter, submitted_for=recipient)
    evaluation = _evaluation(handed_off)
    recipient_note = ApplicationNote.objects.create(job=handed_off, note='recipient note', created_by=recipient)
    followup = _followup(handed_off)

    r = submitter_client.delete('/api/auth/account/', {'password': 'pw'}, format='json')
    assert r.status_code == 200, r.data

    handed_off.refresh_from_db()
    assert handed_off.submitted_for_id == recipient.id
    assert handed_off.created_by_id is None, 'submitter row is gone (SET_NULL); "Added by" loses the name, not the job'
    assert JobEvaluation.objects.filter(pk=evaluation.pk).exists()
    assert ApplicationNote.objects.filter(pk=recipient_note.pk, created_by=recipient).exists()
    assert FollowUp.objects.filter(pk=followup.pk).exists()
    assert not User.objects.filter(username='submitter').exists()

    # Cross-agent tripwire: the recipient must still see the job through the one ownership rule.
    assert list(access.accessible_jobs(recipient)) == [handed_off]


# Watch-for: a note the submitter wrote on a job they do not own must not become a second route
# for deleting the recipient's data -- it survives, only the byline is stripped.

def test_authors_own_note_on_someone_elses_job_is_anonymised_not_deleted(submitter, recipient, submitter_client):
    handed_off = JobLead.objects.create(company='Friend Co', title='Referral', created_by=submitter, submitted_for=recipient)
    submitter_note = ApplicationNote.objects.create(job=handed_off, note='left for the recipient', created_by=submitter)

    r = submitter_client.delete('/api/auth/account/', {'password': 'pw'}, format='json')
    assert r.status_code == 200, r.data

    submitter_note.refresh_from_db()
    assert submitter_note.job_id == handed_off.pk, 'the note itself must survive'
    assert submitter_note.created_by is None, 'only the authorship is stripped, not the content'
    assert JobLead.objects.filter(pk=handed_off.pk).exists()


# AC4 -- the returned summary counts what .delete() actually removed, including cascades, and
# never counts a note that only got anonymised (not deleted).

def test_deletion_summary_counts_only_what_was_actually_deleted(submitter, recipient, submitter_client):
    own_job = JobLead.objects.create(company='Own Co', title='Own Role', created_by=submitter)
    _evaluation(own_job)
    ApplicationNote.objects.create(job=own_job, note='mine', created_by=submitter)
    _followup(own_job)

    handed_off = JobLead.objects.create(company='Friend Co', title='Referral', created_by=submitter, submitted_for=recipient)
    ApplicationNote.objects.create(job=handed_off, note='not deleted, just anonymised', created_by=submitter)

    r = submitter_client.delete('/api/auth/account/', {'password': 'pw'}, format='json')
    assert r.status_code == 200, r.data
    assert r.data['deleted'] == {'jobs': 1, 'evaluations': 1, 'notes': 1, 'followups': 1, 'profile': 0}


# The password gate must keep working: a wrong or missing password deletes nothing.

def test_wrong_password_deletes_nothing(submitter, submitter_client):
    job = JobLead.objects.create(company='Own Co', title='Own Role', created_by=submitter)

    r = submitter_client.delete('/api/auth/account/', {'password': 'not-the-password'}, format='json')

    assert r.status_code == 400
    assert User.objects.filter(username='submitter').exists()
    assert JobLead.objects.filter(pk=job.pk).exists()


def test_missing_password_deletes_nothing(submitter, submitter_client):
    r = submitter_client.delete('/api/auth/account/', {}, format='json')

    assert r.status_code == 400
    assert User.objects.filter(username='submitter').exists()
