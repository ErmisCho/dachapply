"""TASK-368: real experiment/service paths with fake providers only."""
import copy
import json
import shutil

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError

from jobradar.models import JobLead, UserProfile
from jobradar.services import application_prep as prep, benchmark as bench, benchmark_fit_requirements as fit, job_evaluator as evaluator
from jobradar.services.json_importer import LIST_FIELDS, REQ
from jobradar.tests.test_benchmark import exported

POSTING = ('We hire a Python engineer. Tasks: build APIs. Requirements: Python. Salary EUR 60000. '
           'Please apply in German. A cover letter is required. Do not send a motivation letter.')


def answer(job_id):  # TASK-368
    ev = {k: [] if k in LIST_FIELDS else 'Evidence' for k in REQ}
    ev.update(job_id=job_id, fit_score=80, priority='high', recommendation='apply', missing_parts=[])
    req = dict(posting_language='en', application_language='de', application_language_quote='Please apply in German', documents=[
        dict(type='cover_letter', name='', status='required', quote='A cover letter is required'),
        dict(type='motivation_letter', name='', status='not_accepted', quote='Do not send a motivation letter')])
    return {'evaluations': [ev], 'application_requirements': req}


@pytest.fixture
def workload(db, monkeypatch):  # TASK-368
    user = User.objects.create(username='fit-owner')
    UserProfile.whole.update_or_create(user=user, defaults={'candidate_profile': 'Python engineer', 'candidate_evidence': 'Python'})
    job = JobLead.objects.create(created_by=user, company='Example', title='Engineer', original_source_text=POSTING)
    options = [{'provider': 'openai', 'key': 'fake', 'efforts': ['high'], 'default_effort': 'high'}]
    monkeypatch.setattr(prep, 'available_model_options', lambda: options)
    monkeypatch.setattr(prep, 'cv_default_choice', lambda opts: (opts[0], 'high'))
    monkeypatch.setattr(prep, 'validate_model_capability', lambda *a: {})
    monkeypatch.setattr(evaluator, 'validate_model_capability', lambda *a: {})
    calls = []

    def model(prompt, schema, provider, model, effort='default', speed='normal', **kwargs):
        calls.append((schema, provider, model, effort, speed, prompt))
        data = answer(job.pk)
        return {k: data[k] for k in schema['properties']}

    monkeypatch.setattr(prep, 'run_structured_model', model)
    monkeypatch.setattr(evaluator, 'run_structured_model', model)
    return user, job, calls


@pytest.mark.parametrize('variant,count', [('separate', 2), ('combined', 1)])
def test_matched_requests_grounding_and_no_writes(workload, variant, count):  # TASK-368
    user, job, calls = workload
    before = JobLead.objects.values().get(pk=job.pk)
    row = fit.run([job], user, 1, variant)[0]
    assert not row['reason'] and not row['skip']
    assert row['fit']['fit_score'] == 80
    assert row['requirements']['application_language'] == 'de'
    assert [d['status'] for d in row['requirements']['documents']] == ['required', 'not_accepted']
    assert len(calls) == len(row['requests']) == count
    assert {tuple(c[1:5]) for c in calls} == {('openai', 'fake', 'high', 'normal')}
    assert all(q['job_id'] == job.pk and q['end'] >= q['start'] for q in row['requests'])
    assert row['elapsed_seconds'] >= 0
    assert JobLead.objects.values().get(pk=job.pk) == before and not job.evaluations.exists()


@pytest.mark.parametrize('variant', ['separate', 'combined'])
def test_owner_requirements_reused(workload, variant):  # TASK-368
    user, job, calls = workload
    job.application_requirements = {**answer(job.pk)['application_requirements'], 'source': 'owner', 'application_language': 'en'}
    job.save()
    row = fit.run([job], user, 1, variant)[0]
    assert len(calls) == 1 and row['requirements_reused']
    assert row['requirements'] == job.application_requirements


@pytest.mark.parametrize('variant', ['separate', 'combined'])
@pytest.mark.parametrize('case', ['skip', 'missing', 'ungrounded', 'ambiguous'])
def test_skip_missing_and_ambiguous_posting(workload, monkeypatch, variant, case):  # TASK-368
    user, job, calls = workload
    data = answer(job.pk)
    if case == 'skip':
        data['evaluations'][0]['recommendation'] = 'skip'
    if case == 'missing':
        JobLead.objects.filter(pk=job.pk).update(original_source_text='', raw_description='')
        data['evaluations'][0]['missing_parts'] = ['tasks', 'requirements']
    if case == 'ambiguous':
        data['application_requirements']['documents'].append({**data['application_requirements']['documents'][0], 'status': 'not_accepted'})
    if case == 'ungrounded':
        data['application_requirements']['application_language_quote'] = 'invented'
        data['application_requirements']['documents'][0]['quote'] = 'invented'

    def model(prompt, schema, provider, model, effort='default', speed='normal', **kwargs):
        calls.append(schema)
        return copy.deepcopy({k: data[k] for k in schema['properties']})
    monkeypatch.setattr(prep, 'run_structured_model', model)
    monkeypatch.setattr(evaluator, 'run_structured_model', model)
    row = fit.run([job], user, 1, variant)[0]
    assert not row['reason']
    if case == 'skip':
        assert row['skip'] and not row['requirements'] and len(calls) == 1
    elif case in ('missing', 'ungrounded'):
        assert not row['requirements']['application_language']
        assert row['requirements']['documents'][0]['status'] == 'unclear'
        if case == 'missing':
            assert not row['posting']['usable'] and row['fit']['missing_parts'] == ['tasks', 'requirements']
    else:
        assert row['requirements']['documents'][0]['status'] == 'unclear'


@pytest.mark.parametrize('variant', ['separate', 'combined'])
@pytest.mark.parametrize('change', ['source', 'owner', 'pending', 'cancel'])
def test_late_changes_and_cancellation(workload, monkeypatch, variant, change):  # TASK-368
    user, job, calls = workload
    stopped = False
    def model(prompt, schema, provider, model, effort='default', speed='normal', **kwargs):
        nonlocal stopped
        if change == 'source':
            JobLead.objects.filter(pk=job.pk).update(original_source_text=POSTING + ' Updated')
        elif change == 'owner':
            JobLead.objects.filter(pk=job.pk).update(application_requirements={'source': 'owner', 'posting_language': 'de'})
        elif change == 'pending':
            JobLead.objects.filter(pk=job.pk).update(pending_source_text='Alternative posting')
        else:
            stopped = True
        return {k: answer(job.pk)[k] for k in schema['properties']}
    monkeypatch.setattr(prep, 'run_structured_model', model)
    monkeypatch.setattr(evaluator, 'run_structured_model', model)
    if change == 'cancel':
        with pytest.raises(prep.GenerationCancelled):
            fit.run([job], user, 1, variant, cancelled=lambda: stopped)
    else:
        row = fit.run([job], user, 1, variant)[0]
        assert 'changed' in row['reason'] and row['fit'] is None


@pytest.mark.parametrize('bad', ['extra', 'id', 'duplicate', 'score', 'quote_type'])
def test_strict_combined_rejection_and_job_failure_isolation(workload, monkeypatch, bad):  # TASK-368
    user, job, calls = workload
    other = JobLead.objects.create(created_by=user, company='Other', title='Other', original_source_text=POSTING)
    def model(prompt, schema, provider, model, effort='default', speed='normal', **kwargs):
        data = answer(job.pk if not calls else other.pk)
        if not calls:
            if bad == 'extra': data['extra'] = 'unexpected'
            if bad == 'id': data['evaluations'][0]['job_id'] = other.pk
            if bad == 'duplicate': data['evaluations'] *= 2
            if bad == 'score': data['evaluations'][0]['fit_score'] = True
            if bad == 'quote_type': data['application_requirements']['documents'][0]['quote'] = []
        calls.append(prompt)
        return data
    monkeypatch.setattr(prep, 'run_structured_model', model)
    rows = fit.run([job, other], user, 1, 'combined')
    assert rows[0]['reason'] and not rows[1]['reason'] and len(calls) == 2
    assert not job.evaluations.exists() and not other.evaluations.exists()


def test_pending_source_and_access_do_not_call_provider(workload):  # TASK-368
    user, job, calls = workload
    job.pending_source_text = 'Pending'
    job.save()
    foreign = JobLead.objects.create(company='Foreign', title='Foreign')
    rows = fit.run([job, foreign], user, 1, 'combined')
    assert all(r['reason'] for r in rows) and calls == []
    with pytest.raises(CommandError):
        fit.run([job], user, 1, 'unknown')


@pytest.mark.parametrize('variant', ['separate', 'combined'])
def test_provider_failure_is_recorded_and_isolated(workload, monkeypatch, variant):  # TASK-368
    user, job, calls = workload
    other = JobLead.objects.create(created_by=user, company='Other', title='Other', original_source_text=POSTING)
    def model(prompt, schema, provider, model, effort='default', speed='normal', **kwargs):
        calls.append(prompt)
        if len(calls) == 1:
            raise evaluator.RecoverableGenerationError('quota', usage_limit=True)
        data = answer(other.pk)
        return {k: data[k] for k in schema['properties']}
    monkeypatch.setattr(prep, 'run_structured_model', model)
    monkeypatch.setattr(evaluator, 'run_structured_model', model)
    rows = fit.run([job, other], user, 1, variant)
    assert rows[0]['reason'] and not rows[1]['reason']
    assert rows[0]['requests'][0]['error_class'] == 'provider-limit'
    assert rows[0]['requests'][0]['status'] == 'error'


def test_harness_and_paired_review(exported, tmp_path, monkeypatch):  # TASK-368
    fixture, owner = exported
    rows = json.loads((fixture / 'jobs.json').read_text())
    for row in rows:
        row['application_requirements'] = {}
        row['original_source_text'] = POSTING
    (fixture / 'jobs.json').write_text(json.dumps(rows))
    JobLead.objects.filter(created_by=owner).delete()
    User.objects.filter(pk=owner.pk).delete()
    model_name = bench.gen.CV_DEFAULT_MODEL[1]
    options = [{'provider': 'openai', 'key': model_name, 'efforts': ['high'], 'default_effort': 'high'}]
    monkeypatch.setattr(prep, 'available_model_options', lambda: options)
    monkeypatch.setattr(prep, 'validate_model_capability', lambda *a: {})
    monkeypatch.setattr(evaluator, 'validate_model_capability', lambda *a: {})
    def model(prompt, schema, provider, model, effort='default', speed='normal', **kwargs):
        job = JobLead.objects.order_by('pk').first()
        # TASK-368: locate the job in the prompt rather than predicting scratch primary keys.
        import re
        match = re.search(r'Job ID: (\d+)', prompt)
        data = answer(int(match.group(1)) if match else job.pk)
        return {k: data[k] for k in schema['properties']}
    monkeypatch.setattr(prep, 'run_structured_model', model)
    monkeypatch.setattr(evaluator, 'run_structured_model', model)
    results = []
    for variant in ('separate', 'combined'):
        result = bench.run_fixture(fixture, 'fit_requirements', variant, 1, tmp_path / variant)
        results.append(result)
        assert all(not s['reason'] for s in result['states']), [s['reason'] for s in result['states']]
        assert len(result['requests']) == (4 if variant == 'separate' else 2)
        assert (tmp_path / variant / 'review.md').exists()
        JobLead.objects.all().delete()
        User.objects.all().delete()
        shutil.rmtree(result['workspace'])
    call_command('benchmark_fit_review', separate=str(tmp_path / 'separate'), combined=str(tmp_path / 'combined'), out=str(tmp_path / 'paired'))
    review = (tmp_path / 'paired' / 'review.md').read_text()
    assert '| separate | combined |' in review and 'Owner label: pending' in review
    assert 'application_language' in review and 'not_accepted' in review and 'fit_score' in review
    assert '| Requests | 4 | 2 |' in review and '| Repairs | 0 | 0 |' in review
    results[1]['conditions'] = {}
    with pytest.raises(CommandError, match='same fixture'):
        fit.write_review(results, tmp_path)
