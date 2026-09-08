"""TASK-220: evaluating a job through the configured provider instead of copy-paste.

Every test here patches `run_structured_model`, so no provider is ever launched and no API key or
network is needed -- the point of these tests is the wire between the prompt, the response and the
importer, not the model. A test that shelled out to ollama would be a test of the owner's laptop.
"""
import pytest
from unittest.mock import patch

from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from jobradar.models import JobLead, JobEvaluation, UserProfile
from jobradar.services.cv_generator import RecoverableGenerationError
from jobradar.services.job_evaluator import evaluate_jobs

User = get_user_model()


@pytest.fixture
def owner(db):
    user = User.objects.create_user('eval-owner', password='pw')
    UserProfile.objects.create(user=user, candidate_profile='EVAL_FIXTURE_PROFILE backend engineer')
    return user


@pytest.fixture
def job(owner):
    return JobLead.objects.create(company='ACME', title='Python Engineer', raw_description='Python Django SQL', created_by=owner)


def evaluation_for(job, **overrides):
    """A response the paste path would accept, so a rejection in a test is never about a typo here."""
    payload = {
        'job_id': job.id, 'company': job.company, 'title': job.title,
        'fit_score': 82, 'priority': 'high', 'recommendation': 'apply',
        'summary': 'Strong Python overlap.',
        'main_match_reasons': ['Python'], 'main_gaps': ['No Kubernetes'],
        'required_skills': ['Python'], 'nice_to_have_skills': ['Docker'],
        'matched_skills': ['Python'], 'missing_skills': ['Kubernetes'],
        'cv_adjustment_notes': 'Lead with Django.', 'interview_prep_notes': 'Revise indexing.',
        'risk_notes': 'None.', 'next_action': 'Apply this week.',
    }
    payload.update(overrides)
    return payload


# A model the picker would accept. Patched in rather than discovered, because discovery shells out
# to `ollama list` / `lms ls` and would make these tests pass or fail on what the machine has installed.
OLLAMA_OPTION = {'provider': 'ollama', 'key': 'llama3', 'label': 'llama3', 'efforts': ['default'],
                 'default_effort': 'default', 'fast_tier': ''}


def run_with(response, *, job_ids, user, commit=False, provider='ollama', model='llama3',
             effort='default', speed='normal', option=OLLAMA_OPTION):
    with patch('jobradar.services.job_evaluator.validate_model_capability', return_value=option), \
         patch('jobradar.services.job_evaluator.run_structured_model', return_value=response) as runner:
        result = evaluate_jobs(job_ids, user, provider, model, effort, speed, commit=commit)
    return result, runner


def test_accepted_response_is_written_only_when_the_caller_commits(owner, job):
    response = {'evaluations': [evaluation_for(job)]}

    result, runner = run_with(response, job_ids=[job.id], user=owner, commit=True)

    assert result['ok'] is True and result['dry_run'] is False and result['created'] == 1
    stored = JobEvaluation.objects.get(job=job)
    assert (stored.fit_score, stored.priority, stored.recommendation) == (82, 'high', 'apply')
    assert stored.matched_skills == ['Python']
    # The provider was reached through the shared runner, not a second client of this module's own.
    assert runner.call_count == 1


def test_dry_run_is_the_default_and_writes_nothing(owner, job):
    JobEvaluation.objects.create(job=job, fit_score=40, priority='low', recommendation='skip')
    response = {'evaluations': [evaluation_for(job)]}

    result, _ = run_with(response, job_ids=[job.id], user=owner)

    assert result['dry_run'] is True and result['created'] == 0
    assert result['preview'] == [{
        'job_id': job.id, 'company': 'ACME', 'title': 'Python Engineer',
        'fit_score': 82, 'priority': 'high', 'recommendation': 'apply',
        'action': 'replace', 'replaces_fit_score': 40,
    }]
    # The preview described a replacement; the stored evaluation is still the old one.
    assert JobEvaluation.objects.filter(job=job).count() == 1
    assert JobEvaluation.objects.get(job=job).fit_score == 40


def test_dry_run_reports_a_first_evaluation_as_a_creation(owner, job):
    result, _ = run_with({'evaluations': [evaluation_for(job)]}, job_ids=[job.id], user=owner)

    assert result['preview'][0]['action'] == 'create'
    assert result['preview'][0]['replaces_fit_score'] is None


@pytest.mark.parametrize('bad,expected', [
    ({'priority': 'urgent'}, 'priority invalid'),
    ({'recommendation': 'ghost'}, 'recommendation invalid'),
    ({'fit_score': 140}, 'fit_score must be integer 0..100'),
    ({'main_gaps': 'not a list'}, 'main_gaps must be list'),
])
def test_malformed_response_is_rejected_on_the_importers_own_grounds(owner, job, bad, expected):
    """The same complaints the paste path makes, because it is the same validator."""
    result, _ = run_with({'evaluations': [evaluation_for(job, **bad)]}, job_ids=[job.id], user=owner, commit=True)

    assert result['ok'] is False
    assert any(expected in error for error in result['errors']), result['errors']
    assert not JobEvaluation.objects.filter(job=job).exists()


def test_a_response_missing_required_fields_is_rejected_and_writes_nothing(owner, job):
    stripped = {key: value for key, value in evaluation_for(job).items() if key != 'summary'}

    result, _ = run_with({'evaluations': [stripped]}, job_ids=[job.id], user=owner, commit=True)

    assert result['ok'] is False
    assert any('missing' in error and 'summary' in error for error in result['errors']), result['errors']
    assert not JobEvaluation.objects.filter(job=job).exists()


def test_a_response_that_is_not_an_evaluations_list_is_rejected(owner, job):
    result, _ = run_with({'something_else': []}, job_ids=[job.id], user=owner, commit=True)

    assert result['ok'] is False and result['errors'] == ['Root must contain evaluations list']
    assert not JobEvaluation.objects.filter(job=job).exists()


def test_the_validated_model_option_reaches_the_runner(owner, job):
    """Regression: openai at fast speed makes the runner read model_option['fast_tier'].

    The check that a model supports fast speed is the same call that returns the option carrying the
    tier, so a caller that validated and then threw the option away would pass None and crash on
    exactly the combination the validation was meant to make safe.
    """
    fast = {'provider': 'openai', 'key': 'gpt-5', 'label': 'gpt-5', 'efforts': ['low', 'medium', 'high'],
            'default_effort': 'medium', 'fast_tier': 'priority'}

    _, runner = run_with({'evaluations': [evaluation_for(job)]}, job_ids=[job.id], user=owner,
                         provider='openai', model='gpt-5', effort='medium', speed='fast', option=fast)

    assert runner.call_args.kwargs['model_option'] == fast


def test_an_unavailable_model_is_refused_before_the_provider_is_reached(owner, job):
    with patch('jobradar.services.job_evaluator.validate_model_capability',
               side_effect=ValueError('Select an available model for the chosen provider.')), \
         patch('jobradar.services.job_evaluator.run_structured_model') as runner:
        result = evaluate_jobs([job.id], owner, 'ollama', 'not-installed', commit=True)

    assert result['ok'] is False
    assert result['errors'] == ['Select an available model for the chosen provider.']
    assert runner.call_count == 0
    assert not JobEvaluation.objects.exists()


def test_a_provider_failure_surfaces_the_real_error_and_writes_nothing(owner, job):
    boom = RecoverableGenerationError('The selected model could not evaluate the jobs.', 'ollama: model "llama3" not found')

    with patch('jobradar.services.job_evaluator.validate_model_capability', return_value=OLLAMA_OPTION), \
         patch('jobradar.services.job_evaluator.run_structured_model', side_effect=boom):
        result = evaluate_jobs([job.id], owner, 'ollama', 'llama3', commit=True)

    assert result['ok'] is False
    assert result['errors'] == ['The selected model could not evaluate the jobs.']
    # The point of AC5: the owner can tell "model not installed" from "provider refused".
    assert 'not found' in result['detail']
    assert not JobEvaluation.objects.filter(job=job).exists()


def test_a_job_id_that_was_not_selected_is_refused_even_when_the_user_owns_it(owner, job):
    """A model that wanders onto another job must not be able to write to it."""
    other = JobLead.objects.create(company='Other', title='Data Engineer', created_by=owner)

    result, _ = run_with({'evaluations': [evaluation_for(other)]}, job_ids=[job.id], user=owner, commit=True)

    assert result['ok'] is False
    assert any('not one of the selected jobs' in error for error in result['errors']), result['errors']
    assert not JobEvaluation.objects.exists()


def test_another_users_job_cannot_be_evaluated(db, owner, job):
    stranger = User.objects.create_user('eval-stranger', password='pw')
    UserProfile.objects.create(user=stranger, candidate_profile='someone else')

    result, runner = run_with({'evaluations': [evaluation_for(job)]}, job_ids=[job.id], user=stranger, commit=True)

    assert result['ok'] is False
    # Refused before the provider was ever asked -- no prompt containing another user's job is built.
    assert runner.call_count == 0
    assert not JobEvaluation.objects.exists()


def test_endpoint_defaults_to_a_dry_run(owner, job):
    api = APIClient(); api.force_authenticate(owner)
    response = {'evaluations': [evaluation_for(job)]}

    with patch('jobradar.services.job_evaluator.validate_model_capability', return_value=OLLAMA_OPTION), \
         patch('jobradar.services.job_evaluator.run_structured_model', return_value=response):
        r = api.post('/api/jobs/evaluate-with-model/', {'job_ids': [job.id], 'provider': 'ollama', 'model': 'llama3'}, format='json')

    assert r.status_code == 200
    assert r.data['dry_run'] is True and r.data['created'] == 0
    assert not JobEvaluation.objects.exists()


def test_endpoint_reports_a_provider_failure_as_a_400_with_the_detail(owner, job):
    api = APIClient(); api.force_authenticate(owner)
    boom = RecoverableGenerationError('The selected model could not evaluate the jobs.', 'codex: exit status 1')

    with patch('jobradar.services.job_evaluator.validate_model_capability', return_value=OLLAMA_OPTION), \
         patch('jobradar.services.job_evaluator.run_structured_model', side_effect=boom):
        r = api.post('/api/jobs/evaluate-with-model/', {'job_ids': [job.id], 'provider': 'openai', 'model': 'gpt-5', 'commit': True}, format='json')

    assert r.status_code == 400
    assert r.data['ok'] is False and 'exit status 1' in r.data['detail']
    assert not JobEvaluation.objects.exists()
