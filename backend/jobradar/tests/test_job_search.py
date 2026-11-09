"""TASK-362: board search by words, umlaut spelling and small typos."""
import pytest
from django.contrib.auth.models import User
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from jobradar.models import JobLead
from jobradar.services.job_search import search_jobs

JOBS = [
    ('Zühlke', 'Advanced Data Engineer', 'Zürich'),
    ('Zühlke', 'Senior Frontend Developer', 'Hamburg'),
    ('Siemens', 'Cloud Architect', 'München'),
    ('Siemens Healthineers', 'Data Scientist', 'Erlangen'),
    ('SAP', 'Backend Developer Java', 'Walldorf'),
    ('Zalando', 'Software Engineer Payments', 'Berlin'),
    ('Zalando', 'Product Manager', 'Berlin'),
    ('Bosch', 'Embedded Software Entwickler', 'Stuttgart'),
    ('Allianz', 'Data Analyst', 'München'),
    ('Deutsche Bahn', 'DevOps Engineer', 'Frankfurt am Main'),
    ('BMW Group', 'Machine Learning Engineer', 'München'),
    ('Delivery Hero', 'Site Reliability Engineer', 'Berlin'),
    ('N26', 'Security Analyst', 'Berlin'),
    ('Celonis', 'Solutions Consultant', 'München'),
    ('Personio', 'Platform Engineer', 'München'),
    ('Roche', 'Bioinformatics Scientist', 'Basel'),
    ('Novartis', 'IT Project Manager', 'Basel'),
    ('Swisscom', 'Network Engineer', 'Bern'),
    ('Raiffeisen', 'Business Analyst', 'Wien'),
    ('Erste Group', 'Data Platform Lead', 'Wien'),
    ('Müller Logistik', 'Werkstudent Controlling', 'Köln'),
    ('Henkel', 'Junior Consultant SAP', 'Düsseldorf'),
]


@pytest.fixture
def owner(db):
    return User.objects.create_user('search-owner', password='pw')


@pytest.fixture
def jobs(owner):
    return {(c, t): JobLead.objects.create(company=c, title=t, location=loc, created_by=owner, url=f'https://jobs.example.test/{i}',
                                           raw_description=f'We are hiring a {t} in {loc}. Great team, flexible hours.')
            for i, (c, t, loc) in enumerate(JOBS)}


def found(owner, query):
    client = APIClient(); client.force_authenticate(owner)
    response = client.get('/api/jobs/', {'search': query})
    assert response.status_code == 200
    return {(row['company'], row['title']) for row in response.data}


def test_owner_query_mixing_company_typo_and_title_words_finds_the_zuehlke_job(owner, jobs):
    assert found(owner, 'zuelhle advanced data Engineer') == {('Zühlke', 'Advanced Data Engineer')}


def test_every_word_must_match_somewhere(owner, jobs):
    assert found(owner, 'zalando engineer') == {('Zalando', 'Software Engineer Payments')}
    assert found(owner, 'berlin analyst') == {('N26', 'Security Analyst')}  # location + title
    assert found(owner, 'zalando kubernetes') == set()


@pytest.mark.parametrize('query', ['zuehlke', 'zuhlke', 'Zühlke', 'ZÜHLKE'])
def test_umlaut_spellings_find_the_same_jobs(owner, jobs, query):
    assert found(owner, query) == {('Zühlke', 'Advanced Data Engineer'), ('Zühlke', 'Senior Frontend Developer')}


def test_umlaut_spelling_also_matches_the_posting_text(owner, jobs):
    JobLead.objects.filter(company='Bosch').update(raw_description='Erfahrung mit Prüfständen und Größenordnungen.')
    assert found(owner, 'pruefstaenden') == {('Bosch', 'Embedded Software Entwickler')}
    assert found(owner, 'groessenordnungen') == {('Bosch', 'Embedded Software Entwickler')}


@pytest.mark.parametrize('query, expected', [
    ('zuelhle', {('Zühlke', 'Advanced Data Engineer'), ('Zühlke', 'Senior Frontend Developer')}),
    ('siemns', {('Siemens', 'Cloud Architect'), ('Siemens Healthineers', 'Data Scientist')}),
    ('enginer zalando', {('Zalando', 'Software Engineer Payments')}),
    ('devloper', {('Zühlke', 'Senior Frontend Developer'), ('SAP', 'Backend Developer Java')}),
    ('consultnat', {('Celonis', 'Solutions Consultant'), ('Henkel', 'Junior Consultant SAP')}),
])
def test_typo_queries_find_exactly_the_intended_jobs(owner, jobs, query, expected):
    assert found(owner, query) == expected


def test_words_shorter_than_four_letters_are_never_fuzzy(owner, jobs):
    assert found(owner, 'jva') == set()
    assert found(owner, 'BWM') == set()


def test_posting_word_still_matches_in_sql(owner, jobs):
    JobLead.objects.filter(company='Zühlke', title='Advanced Data Engineer').update(raw_description='Kafka and Spark pipelines.')
    assert found(owner, 'zuehlke kafka') == {('Zühlke', 'Advanced Data Engineer')}
    assert found(owner, 'example.test/5') == {('Zalando', 'Software Engineer Payments')}  # url, as before


def test_search_is_one_query_however_many_jobs(owner, jobs):
    with CaptureQueriesContext(connection) as ctx:
        assert len(list(search_jobs(JobLead.objects.all(), 'zuelhle advanced data engineer'))) == 1
    assert len(ctx.captured_queries) == 2  # the matching pass + the filtered queryset itself
