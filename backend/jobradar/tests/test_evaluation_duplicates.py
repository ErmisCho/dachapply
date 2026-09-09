"""TASK-223: one job evaluated twice in a single model response.

Measured on the owner's machine before it was fixed: one job selected, evaluated through
lmstudio / deepseek-r1-distill-qwen-7b, and the dry-run came back with two identical rows for it --
so the commit button offered to "Save 2 evaluations" for one job. The rule `evaluate_jobs` now
applies is REJECT, not collapse; these tests hold it to that rather than to whichever row came first.

No provider is launched here. The fixtures and the response builder are the ones test_job_evaluator
already uses, so a rejection in this file is about the duplicate and never about a different payload.
"""
from jobradar.models import JobEvaluation, JobLead
from jobradar.tests.test_job_evaluator import evaluation_for, job, owner, run_with  # noqa: F401  (pytest fixtures)


def test_the_same_job_twice_is_rejected_rather_than_collapsed(owner, job):
    """The reproduction: one selected job, two entries for it, both plausible."""
    response = {'evaluations': [evaluation_for(job, fit_score=90), evaluation_for(job, fit_score=90)]}

    result, _ = run_with(response, job_ids=[job.id], user=owner)

    assert result['ok'] is False
    assert any('a second time' in error for error in result['errors']), result['errors']
    # No preview at all, so there is no count for the commit button to be wrong about.
    assert 'preview' not in result


def test_a_duplicated_job_id_writes_nothing_even_when_the_caller_commits(owner, job):
    """AC3, counted in the database: the run evaluated the job zero acceptable times, so zero rows."""
    JobEvaluation.objects.create(job=job, fit_score=94, priority='high', recommendation='apply')
    response = {'evaluations': [evaluation_for(job, fit_score=90), evaluation_for(job, fit_score=90)]}

    result, _ = run_with(response, job_ids=[job.id], user=owner, commit=True)

    assert result['ok'] is False
    assert JobEvaluation.objects.filter(job=job).count() == 1
    assert JobEvaluation.objects.get(job=job).fit_score == 94


def test_the_previewed_count_is_the_number_of_rows_a_commit_writes(owner, job):
    """AC2, and the reason the guard is worth having: the number on the button is the number of rows."""
    other = JobLead.objects.create(company='Other', title='Data Engineer', created_by=owner)
    response = {'evaluations': [evaluation_for(job), evaluation_for(other)]}

    result, _ = run_with(response, job_ids=[job.id, other.id], user=owner, commit=True)

    assert result['ok'] is True
    assert len(result['preview']) == result['created'] == JobEvaluation.objects.count() == 2
