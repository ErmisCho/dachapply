"""TASK-283.2: the board list's per-row cache (JobLeadViewSet.list, views.BOARD_ROW_SOURCES).

Every change test loads the board twice first -- the cold fill, then a warm request through the
stamp query -- so the load after the change is served by the cache path, and only a stamp that
moved can make the change visible.
"""
import json

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from jobradar.models import ApplicationNote, JobEvaluation, JobLead, MailboxMessage, MailboxRun
from jobradar.services.cv_tasks import mark_ready_to_submit
from jobradar.views import BOARD_ROW_SOURCES

BOARD = '/api/jobs/?board=1'


def _client(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def _evaluate(job, fit_score, priority='medium', summary='Summary'):
    return JobEvaluation.objects.create(job=job, fit_score=fit_score, priority=priority, recommendation='apply', summary=summary,
                                        required_skills=['Python', 'Kubernetes'], matched_skills=['Python'], missing_skills=['Kubernetes'])


@pytest.fixture
def board(db):
    owner = User.objects.create_user('rc-owner', email='owner@example.test', password='pw')
    friend = User.objects.create_user('rc-friend', email='friend@example.test', password='pw')
    other = User.objects.create_user('rc-other', email='other@example.test', password='pw')
    jobs = {
        'evaluated': JobLead.objects.create(company='Acme', title='Backend engineer', url='https://jobs.example.test/1', created_by=owner),
        'plain': JobLead.objects.create(company='Plain', title='Python developer', url='https://jobs.example.test/2', created_by=owner),
        # A friend's submission for the owner, and the owner's own submission to someone else.
        'from_friend': JobLead.objects.create(company='Friend Co', title='Django developer', url='https://jobs.example.test/3', created_by=friend, submitted_for=owner, source='friend'),
        'given_away': JobLead.objects.create(company='Away Co', title='Platform engineer', url='https://jobs.example.test/4', created_by=owner, submitted_for=other),
        'two_evals': JobLead.objects.create(company='Twice', title='Data engineer', url='https://jobs.example.test/5', created_by=owner),
    }
    _evaluate(jobs['evaluated'], 80, 'high')
    _evaluate(jobs['from_friend'], 70)
    _evaluate(jobs['two_evals'], 60, 'low')
    _evaluate(jobs['two_evals'], 65, 'high')
    ApplicationNote.objects.create(job=jobs['evaluated'], note='Call back\n\nnext week', created_by=owner)
    MailboxMessage.objects.create(run=MailboxRun.objects.create(), uid=1, sender='hr@example.test', subject='Re', matched_job=jobs['evaluated'])
    return {'owner': _client(owner), 'friend': _client(friend), 'other': other, 'jobs': jobs}


def _load(client, url=BOARD):
    response = client.get(url)
    assert response.status_code == 200, response.content
    return response.content


def _rows(client):
    return {row['id']: row for row in json.loads(_load(client))}


@pytest.fixture
def warm(board):
    _load(board['owner']); _load(board['owner'])
    return board


def test_a_job_edit_shows_on_the_next_load(warm):
    job = warm['jobs']['plain']
    assert warm['owner'].patch(f'/api/jobs/{job.pk}/', {'interview_note': 'Ask about on-call'}, format='json').status_code == 200
    assert _rows(warm['owner'])[job.pk]['interview_note'] == 'Ask about on-call'


def test_a_status_written_by_update_shows_on_the_next_load(warm):
    job = warm['jobs']['plain']
    assert mark_ready_to_submit(job.pk) == 1  # one .update(): auto_now does not move
    assert _rows(warm['owner'])[job.pk]['status'] == 'ready_to_submit'


def test_a_new_evaluation_shows_on_the_next_load(warm):
    job = warm['jobs']['plain']
    evaluation = _evaluate(job, 91)
    assert _rows(warm['owner'])[job.pk]['latest_evaluation']['id'] == evaluation.pk


def test_an_evaluation_edit_shows_on_the_next_load(warm):
    evaluation = warm['jobs']['evaluated'].evaluations.get()
    evaluation.summary = 'Rewritten summary'
    evaluation.save()
    assert _rows(warm['owner'])[evaluation.job_id]['latest_evaluation']['summary'] == 'Rewritten summary'


def test_adding_and_blanking_a_general_note_shows_on_the_next_load(warm):
    job = warm['jobs']['plain']
    note = ApplicationNote.objects.create(job=job, note='Recruiter is Anna', created_by=None)
    assert _rows(warm['owner'])[job.pk]['note_preview'] == 'Recruiter is Anna'
    note.note = ''
    note.save()
    assert _rows(warm['owner'])[job.pk]['note_preview'] == ''


def test_a_new_mailbox_match_shows_on_the_next_load(warm):
    job = warm['jobs']['plain']
    assert _rows(warm['owner'])[job.pk]['has_mailbox_history'] is False
    MailboxMessage.objects.create(run=MailboxRun.objects.create(), uid=2, sender='hr@example.test', subject='Interview', matched_job=job)
    assert _rows(warm['owner'])[job.pk]['has_mailbox_history'] is True


def test_renaming_the_submitted_for_user_shows_on_the_next_load(warm):
    other = warm['other']
    other.username, other.email = 'rc-renamed', 'renamed@example.test'
    other.save()
    row = _rows(warm['owner'])[warm['jobs']['given_away'].pk]
    assert (row['submitted_for_username'], row['submitted_for_email']) == ('rc-renamed', 'renamed@example.test')


def test_every_emitted_board_field_has_a_stamp_source(board):
    """A field added to JobLeadListSerializer / JobEvaluationListSerializer (or the submission
    projection) must be mapped in BOARD_ROW_SOURCES, or the cache would serve it stale."""
    emitted = set()
    for client in (board['owner'], board['friend']):
        for row in json.loads(_load(client)):
            emitted |= set(row)
            if row.get('latest_evaluation'):
                emitted |= {f'latest_evaluation.{key}' for key in row['latest_evaluation']}
    assert 'submission_only' in emitted and 'latest_evaluation.summary' in emitted  # the fixture covers both shapes
    assert emitted == set(BOARD_ROW_SOURCES)


@pytest.mark.parametrize('ordering', ['', 'recommended', 'created_at', '-fit_score', 'status,priority', 'priority,-updated_at'])
def test_the_cached_response_is_byte_identical_to_the_uncached_one(board, settings, ordering):
    url = f'{BOARD}&ordering={ordering}'
    cold, warm_hit = _load(board['owner'], url), _load(board['owner'], url)
    settings.CACHES = {alias: config for alias, config in settings.CACHES.items() if alias != 'board_rows'}
    uncached = _load(board['owner'], url)
    assert cold == warm_hit == uncached


def test_each_viewer_gets_their_own_projection(board):
    job = board['jobs']['from_friend']
    for _ in range(2):  # cold, then warm: neither viewer may ever be handed the other's row
        owner_row, friend_row = _rows(board['owner'])[job.pk], _rows(board['friend'])[job.pk]
        assert 'submission_only' not in owner_row and owner_row['latest_evaluation']['fit_score'] == 70
        assert friend_row['submission_only'] is True and friend_row['latest_evaluation'] is None


def test_a_deleted_job_disappears_on_the_next_load(warm):
    job_id = warm['jobs']['plain'].pk
    assert job_id in _rows(warm['owner'])
    JobLead.objects.filter(pk=job_id).delete()
    assert job_id not in _rows(warm['owner'])
