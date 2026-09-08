"""TASK-220: evaluate jobs with the configured provider instead of the ChatGPT copy-paste loop.

The prompt builder, the provider dispatch and the strict importer all already existed. The only
thing missing was the wire between them, and that is all this module is.

Nothing here re-implements validation. `json_importer.validate_eval` decides what an acceptable
evaluation looks like, so a response from a local model is rejected on exactly the grounds a pasted
one would be -- there is no second, laxer parser that only the automated path goes through. The
commit itself is `json_importer.import_evaluations`, unchanged, which is already atomic and already
owner-scopes through `accessible_jobs`.

Dry-run is the default and is not a courtesy: the model picks fit_score, priority and
recommendation, and those drive the board's ordering and the owner's to_apply decision. Writing
them sight-unseen would hand the board's priorities to whatever a local model felt like emitting.
"""
import tempfile

from jobradar.models import JobEvaluation
from jobradar.services.access import accessible_jobs
from jobradar.services.cv_generator import RecoverableGenerationError, run_structured_model, validate_model_capability
from jobradar.services.json_importer import REQ, LIST_FIELDS, import_evaluations, validate_eval
from jobradar.services.prompt_builder import build_candidate_profile_text, build_prompt, user_profile_settings

# Derived from the importer's own REQ set rather than typed out again, so a field added to the
# evaluation contract cannot be required by the importer and missing from the schema we hand the
# model -- that mismatch would show up as a confusing model failure rather than as a code change.
_STRING_FIELDS = sorted(REQ - set(LIST_FIELDS) - {'job_id', 'fit_score', 'priority', 'recommendation'})

EVALUATION_SCHEMA = {
    'type': 'object',
    'properties': {
        'evaluations': {
            'type': 'array',
            'items': {
                'type': 'object',
                'properties': {
                    'job_id': {'type': 'integer'},
                    'fit_score': {'type': 'integer', 'minimum': 0, 'maximum': 100},
                    'priority': {'type': 'string', 'enum': ['high', 'medium', 'low']},
                    'recommendation': {'type': 'string', 'enum': ['apply', 'maybe', 'skip']},
                    **{field: {'type': 'string'} for field in _STRING_FIELDS},
                    **{field: {'type': 'array', 'items': {'type': 'string'}} for field in LIST_FIELDS},
                },
                'required': sorted(REQ),
                'additionalProperties': False,
            },
        },
    },
    'required': ['evaluations'],
    'additionalProperties': False,
}


def _preview_row(job, ev):
    """What committing this evaluation would do to this job, in the board's own terms.

    `create_evaluation` always inserts a row, so "update" is never literally true at the database
    level -- but JobEvaluation.Meta orders by -created_at and the board reads the newest one, so an
    evaluation landing on a job that already has one does replace what the owner sees. Reporting
    that as `create` would be technically accurate and practically a lie.
    """
    current = JobEvaluation.objects.filter(job=job).order_by('-created_at').first()
    return {
        'job_id': job.id,
        'company': job.company,
        'title': job.title,
        'fit_score': ev['fit_score'],
        'priority': ev['priority'],
        'recommendation': ev['recommendation'],
        'action': 'replace' if current else 'create',
        'replaces_fit_score': current.fit_score if current else None,
    }


def evaluate_jobs(job_ids, user, provider, model, effort='default', speed='normal', commit=False, cancelled=None):
    """Evaluate `job_ids` with the configured provider. Writes nothing unless `commit` is true.

    Returns the same {'ok': False, 'errors': [...]} shape the paste path returns, plus a `detail`
    carrying the provider's real stderr when the failure came from the provider rather than from
    the response's contents.
    """
    jobs = list(accessible_jobs(user).filter(id__in=job_ids))
    if not jobs:
        return {'ok': False, 'errors': ['No jobs you can evaluate were selected.'], 'detail': ''}

    # Validated here rather than in the view because the runner needs what this returns: for
    # openai at fast speed it reads model_option['fast_tier'], so a caller that only checked the
    # combination and threw the option away would hand the runner None and crash on the one path
    # the check was supposed to make safe.
    try:
        model_option = validate_model_capability(provider, model, effort, speed)
    except ValueError as exc:
        return {'ok': False, 'errors': [str(exc)], 'detail': ''}

    # The same prompt the copy-paste path hands the user, built the same way -- including the
    # owner's saved evaluation template, so the automated path cannot quietly evaluate against
    # different instructions than the ones they tuned in /prompts.
    profile = user_profile_settings(user)
    prompt = build_prompt(jobs, '', build_candidate_profile_text(user), profile.evaluation_prompt_template)
    try:
        with tempfile.TemporaryDirectory(prefix='dachapply-eval-') as workdir:
            data = run_structured_model(prompt, EVALUATION_SCHEMA, provider, model, effort, speed,
                                        workdir=workdir, cancelled=cancelled, model_option=model_option)
    except RecoverableGenerationError as exc:
        # The provider's own words, not a generic failure: a missing ollama model and an out-of-quota
        # API key are different problems and the owner can only act on the difference.
        return {'ok': False, 'errors': [exc.summary], 'detail': exc.diagnostics}

    if not isinstance(data, dict) or not isinstance(data.get('evaluations'), list):
        return {'ok': False, 'errors': ['Root must contain evaluations list'], 'detail': ''}

    # Validated with the importer's own function, before anything is written and regardless of
    # whether this is a dry run -- a preview built from an invalid response would be a preview of
    # something that can never be committed.
    requested = {job.id: job for job in jobs}
    errors = []
    for i, ev in enumerate(data['evaluations']):
        errors += validate_eval(ev, i, require_job_id=True)
        if isinstance(ev, dict) and ev.get('job_id') not in requested:
            # A model that invents or wanders onto another job_id must not be able to write to it,
            # even when that job would pass the importer's own ownership check.
            errors.append(f'evaluation[{i}].job_id was not one of the selected jobs: {ev.get("job_id")}')
    if errors:
        return {'ok': False, 'errors': errors, 'detail': ''}

    preview = [_preview_row(requested[ev['job_id']], ev) for ev in data['evaluations']]
    if not commit:
        return {'ok': True, 'dry_run': True, 'preview': preview, 'created': 0, 'errors': []}

    result = import_evaluations(data, user=user)
    if not result.get('ok'):
        return {'ok': False, 'errors': result.get('errors', []), 'detail': ''}
    return {'ok': True, 'dry_run': False, 'preview': preview, 'created': result.get('count', 0), 'errors': []}
