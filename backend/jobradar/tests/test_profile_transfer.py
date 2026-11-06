"""TASK-354: polled and per-request paths must not download the big profile columns.

Neon transfer hit 81% of 5 GB on the 6th of the month: 761 of 779 requests loaded the whole 186 KB
profile row. The endpoint tests run the real request, keep every SELECT, and fail if one names a
large column. Bytes are measured by running those SELECTs again and adding up what comes back.
"""
import re
from unittest import mock

import pytest
from django.contrib.auth.models import User
from django.db import connection
from django.test import Client

from jobradar.models import JobLead, UserProfile
from jobradar.services import cv_tasks
from jobradar.services.cv_generator import is_cv_owner
from jobradar.services.prompt_builder import build_candidate_profile_text, user_profile_settings

LARGE = ('learned_application_preferences', 'candidate_profile', 'candidate_evidence', 'evaluation_prompt_template',
         'combined_prompt_template', 'enrichment_prompt_template', 'bulk_links_prompt_template')
PREFERENCES = '\n'.join(f'- [CV] Preference number {i} {"x" * 60}' for i in range(2200))[:176_497]
PROFILE = 'Backend engineer. ' + 'p' * 9_100 + ' END-OF-PROFILE'
EVIDENCE = 'Evidence ' + 'e' * 5_000 + ' END-OF-EVIDENCE'
TEMPLATE = 'Custom prompt {candidate_profile} {jobs} {custom_instructions} ' + 't' * 2_000
# The bytes a poll may still read: session, user, a few jobs and the small profile columns.
SMALL_POLL = 18_000

ENDPOINTS = {
    'queue': '/api/jobs/application-prep/queue/',
    'active': '/api/jobs/application-prep/active/',
    'stats': '/api/stats/',
    'board_list': '/api/jobs/?status=new,reviewed,to_apply&ordering=recommended&board=1',
    'me': '/api/auth/me/',
    'job_detail': '/api/jobs/{job}/',
    'prep_status': '/api/jobs/{job}/application-prep/',
    'cv_task_status': '/api/cv-generation/tasks/fake-task/',
}


@pytest.fixture
def owner(db, settings):
    settings.CODEX_CV_ENABLED = True
    user = User.objects.create_user('t354', email='t354@example.test', password='pw', is_staff=True)
    UserProfile.objects.create(
        user=user, can_generate_cv=True, learned_application_preferences=PREFERENCES, candidate_profile=PROFILE,
        candidate_evidence=EVIDENCE, evaluation_prompt_template=TEMPLATE, combined_prompt_template=TEMPLATE,
        enrichment_prompt_template=TEMPLATE, bulk_links_prompt_template=TEMPLATE)
    return user


@pytest.fixture
def client(owner):
    JobLead.objects.create(company='Acme', title='Engineer', url='https://jobs.example.test/1', status='to_apply', created_by=owner)
    client = Client()
    client.force_login(owner)
    client.cookies['app_sessionid'] = client.cookies['sessionid'].value
    del client.cookies['sessionid']
    client.get('/api/auth/me/')  # the visitor cookie, so what is measured is a repeat visit
    return client


def fetched(client, url):
    """Every SELECT the request ran, as (sql, params); the response must succeed."""
    selects = []

    def keep(execute, sql, params, many, context):
        if sql.lstrip().upper().startswith('SELECT') and 'sqlite_master' not in sql:
            selects.append((sql, params))
        return execute(sql, params, many, context)

    with mock.patch('jobradar.views.get_cv_task', lambda task_id, user_id: {'id': task_id}), connection.execute_wrapper(keep):
        response = client.get(url)
    assert response.status_code == 200, (url, response.content[:300])
    return selects


def bytes_read(selects):
    total = 0
    with connection.cursor() as cursor:
        for sql, params in selects:
            cursor.execute(sql, params)
            total += sum(len(str(value).encode()) for row in cursor.fetchall() for value in row if value is not None)
    return total


def large_columns(selects):
    # me reads the first 65 characters of candidate_profile through SUBSTR, to tell empty from filled.
    text = ' '.join(re.sub(r'SUBSTR(?:ING)?\([^)]*\)', '', sql, flags=re.I) for sql, _ in selects)  # SUBSTRING on Postgres
    return sorted({column for column in LARGE if f'"{column}"' in text})


@pytest.mark.parametrize('name', ENDPOINTS)
def test_endpoint_reads_no_large_profile_column(client, name):
    selects = fetched(client, ENDPOINTS[name].format(job=JobLead.objects.get().id))
    assert large_columns(selects) == []


@pytest.mark.parametrize('name', ENDPOINTS)
def test_endpoint_reads_few_bytes(client, name):
    assert bytes_read(fetched(client, ENDPOINTS[name].format(job=JobLead.objects.get().id))) < SMALL_POLL


def test_queue_poll_reads_at_least_90_percent_fewer_bytes_than_the_whole_row(client):
    assert len(PREFERENCES.encode()) == 176_497
    with connection.cursor() as cursor:
        cursor.execute('SELECT * FROM jobradar_userprofile')
        whole_row = sum(len(str(value).encode()) for value in cursor.fetchone() if value is not None)
    assert bytes_read(fetched(client, ENDPOINTS['queue'])) <= whole_row * 0.1


def test_every_ordinary_loader_leaves_the_large_columns_out(owner):
    expected = set(LARGE)
    assert UserProfile.objects.get(user=owner).get_deferred_fields() == expected
    assert user_profile_settings(owner).get_deferred_fields() == expected
    assert User.objects.get(pk=owner.pk).jobradar_profile.get_deferred_fields() == expected
    assert User.objects.prefetch_related('jobradar_profile').get(pk=owner.pk).jobradar_profile.get_deferred_fields() == expected
    assert UserProfile.whole.get(user=owner).get_deferred_fields() == set()
    assert user_profile_settings(owner, whole=True).get_deferred_fields() == set()


def test_a_deferred_read_still_gets_the_whole_text(owner):
    profile = user_profile_settings(owner)
    assert profile.learned_application_preferences == PREFERENCES
    assert profile.candidate_evidence == EVIDENCE
    assert build_candidate_profile_text(owner).endswith('END-OF-PROFILE')


def test_saving_a_partial_profile_keeps_the_large_columns(owner):
    profile = User.objects.get(pk=owner.pk).jobradar_profile
    profile.target_roles = 'Backend'
    profile.save()
    stored = UserProfile.whole.get(user=owner)
    assert (stored.target_roles, stored.learned_application_preferences, stored.candidate_profile) == ('Backend', PREFERENCES, PROFILE)


def test_learning_a_preference_keeps_all_the_text_and_a_cached_partial_sees_it(owner):
    user = User.objects.get(pk=owner.pk)
    assert is_cv_owner(user)  # leaves the partial profile cached on user.jobradar_profile
    entry = cv_tasks._learn_application_preference(owner.id, 'Keep bullets short', True, False)
    assert entry == '- [CV] Keep bullets short'
    assert user.jobradar_profile.learned_application_preferences == f'{PREFERENCES}\n{entry}'
    assert UserProfile.whole.get(user=owner).learned_application_preferences == f'{PREFERENCES}\n{entry}'
    cv_tasks._learn_application_preference(owner.id, 'Keep bullets short', True, False)
    assert UserProfile.whole.get(user=owner).learned_application_preferences == f'{PREFERENCES}\n{entry}'


def test_learning_a_preference_on_a_new_account_creates_the_row(db):
    user = User.objects.create_user('t354-new', password='pw')
    entry = cv_tasks._learn_application_preference(user.id, 'Be brief', False, True)
    assert UserProfile.whole.get(user=user).learned_application_preferences == entry


def test_profile_page_reads_and_saves_the_large_fields_in_one_query(client, owner):
    url = '/api/profile/'
    selects = [sql for sql, _ in fetched(client, url) if 'jobradar_userprofile' in sql]
    assert len(selects) == 1  # not one more per deferred column
    data = client.get(url).json()
    assert data['learned_application_preferences'] == PREFERENCES
    assert data['candidate_evidence'] == EVIDENCE
    assert data['evaluation_prompt_template'] == TEMPLATE

    response = client.patch(url, {'target_roles': 'Staff engineer', 'candidate_evidence': EVIDENCE + ' more'}, content_type='application/json')
    assert response.status_code == 200, response.content
    assert response.json()['learned_application_preferences'] == PREFERENCES
    stored = UserProfile.whole.get(user=owner)
    assert stored.candidate_evidence == EVIDENCE + ' more'
    assert stored.learned_application_preferences == PREFERENCES
    assert stored.candidate_profile == PROFILE


def test_prompts_receive_the_whole_profile_and_the_custom_template(client):
    job = JobLead.objects.get()
    response = client.post('/api/prompts/generate/', {'job_ids': [job.id]}, content_type='application/json')
    assert response.status_code == 200, response.content
    prompt = response.json()['generated_prompt']
    assert 'END-OF-PROFILE' in prompt and prompt.startswith('Custom prompt')
