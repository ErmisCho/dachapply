"""TASK-368: scratch-only fit/requirements comparison; never imported by application flows."""
import json
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

from django.core.management.base import CommandError

from jobradar.services import application_prep as prep, job_evaluator as evaluator
from jobradar.services.access import accessible_jobs
from jobradar.services.application_requirements import normalize_application_requirements
from jobradar.services.prompt_builder import APPLICATION_REQUIREMENTS_RULES, build_candidate_profile_text, build_prompt, user_profile_settings

COMBINED_SCHEMA = {  # TASK-368: compose the original strict contracts without weakening either.
    'type': 'object', 'additionalProperties': False,
    'required': ['evaluations', 'application_requirements'],
    'properties': {**evaluator.EVALUATION_SCHEMA['properties'], **prep.REQUIREMENTS_SCHEMA['properties']},
}


def _validate(value, schema):  # TASK-368: reject malformed fake/provider answers before normalisation.
    kind = schema['type']
    valid = {'object': isinstance(value, dict), 'array': isinstance(value, list),
             'string': isinstance(value, str), 'integer': type(value) is int}[kind]
    if not valid or ('enum' in schema and value not in schema['enum']):
        raise ValueError('Response does not match the strict schema')
    if kind == 'object':
        if set(schema['required']) - value.keys() or value.keys() - schema['properties'].keys():
            raise ValueError('Response has missing or unexpected fields')
        for key, item in value.items():
            _validate(item, schema['properties'][key])
    elif kind == 'array':
        for item in value:
            _validate(item, schema['items'])
    elif kind == 'integer' and not schema.get('minimum', value) <= value <= schema.get('maximum', value):
        raise ValueError('Response integer is outside the strict schema range')


def run(jobs, user, workers, variant, cancelled=None):  # TASK-368: sequential matched per-job workload, no writes.
    from jobradar.services.benchmark import Recorder, error_class
    if variant not in ('separate', 'combined'):
        raise CommandError('fit_requirements requires --variant separate or combined.')
    option, effort = prep.cv_default_choice(prep.available_model_options())
    if not option:
        raise CommandError(prep.NO_MODEL)
    provider, model = option['provider'], option['key']
    model_option = prep.validate_model_capability(provider, model, effort, 'normal')
    states = []
    recorder = Recorder(tempfile.gettempdir())
    original = evaluator.run_structured_model
    with patch.object(prep, 'run_structured_model', recorder.model(prep.run_structured_model)):
        for supplied in jobs:
            started, first = time.monotonic(), len(recorder.requests)
            row = {'job_id': supplied.pk, 'variants': {}, 'fit': None, 'requirements': {}, 'reason': '', 'error_class': None}
            recorder.context.identity = {'job_id': supplied.pk, 'user_id': user.pk}
            try:
                if cancelled and cancelled():
                    raise prep.GenerationCancelled
                job = accessible_jobs(user).get(pk=supplied.pk)
                source, stored = job.source_text, job.application_requirements
                if job.pending_source_text:
                    raise ValueError(prep.CHOOSE_SOURCE)
                requirements = normalize_application_requirements(stored, job)
                row['requirements'] = requirements
                row['requirements_reused'] = bool(requirements)
                row['posting'] = {'usable': job.is_meaningful_source(source), 'chars': len(source)}
                data = None
                if variant == 'combined' and not requirements:
                    profile = user_profile_settings(user)
                    prompt = build_prompt([job], '', build_candidate_profile_text(user), profile.evaluation_prompt_template)
                    prompt += ('\n\nAlso return application_requirements beside evaluations, using the same posting.\n'
                               + APPLICATION_REQUIREMENTS_RULES + '\nReturn JSON matching the supplied combined schema.')
                    with tempfile.TemporaryDirectory(prefix='dachapply-fit-requirements-') as workdir:
                        data = prep.run_structured_model(prompt, COMBINED_SCHEMA, provider, model, effort, 'normal',
                            workdir=workdir, model_option=model_option, cancelled=cancelled)
                    _validate(data, COMBINED_SCHEMA)

                def fit_model(*args, **kwargs):
                    nonlocal data
                    if data is None:
                        data = recorder.model(original)(*args, **kwargs)
                        _validate(data, evaluator.EVALUATION_SCHEMA)
                    return {'evaluations': data['evaluations']}

                # TASK-368: replay the combined fit through today's importer validation, without a second request.
                with patch.object(evaluator, 'run_structured_model', fit_model):
                    result = evaluator.evaluate_jobs([job.pk], user, provider, model, effort, 'normal', cancelled=cancelled)
                if not result['ok']:
                    raise ValueError('; '.join(result['errors']))
                if len(data['evaluations']) != 1:
                    raise ValueError('Expected exactly one fit result for the selected job')
                row['fit'] = data['evaluations'][0]
                row['skip'] = row['fit']['recommendation'] == 'skip' and job.status not in prep.OWNER_CHOSEN
                if not requirements and not row['skip']:
                    requirements = (normalize_application_requirements(data['application_requirements'], job, source='analysis')
                                    if variant == 'combined' else prep._analyse(job, cancelled=cancelled))
                    if not requirements:
                        raise ValueError('Model returned no application requirements')
                job.refresh_from_db()
                if job.source_text != source or job.application_requirements != stored or job.pending_source_text:
                    row['fit'] = None
                    raise ValueError('Posting or owner requirements changed during analysis; discard this result')
                if cancelled and cancelled():
                    row['fit'] = None
                    raise prep.GenerationCancelled
                row['requirements'] = requirements
                row['planned'], row['planning_reason'] = prep.plan_variants(requirements)
            except prep.GenerationCancelled:
                raise  # TASK-368: never start another job after cancellation.
            except Exception as exc:
                row.update(reason=str(exc), error_class=error_class(exc))
            row.update(elapsed_seconds=time.monotonic() - started, requests=recorder.requests[first:])
            states.append(row)
    return states


def write_review(results, output):  # TASK-368: pair separate runs; unmeasured cells are explicitly empty.
    by_variant = {r['variant']: r for r in results}
    if len(by_variant) != len(results) or not set(by_variant) <= {'separate', 'combined'}:
        raise CommandError('Supply at most one run of each fit_requirements variant.')
    if any(r['experiment'] != 'fit_requirements' for r in results):
        raise CommandError('Expected fit_requirements results.')
    if len(results) == 2 and any(results[0][key] != results[1][key] for key in ('fixture', 'conditions')):
        raise CommandError('Comparison requires the same fixture and model conditions.')
    mapped = {v: {str(original): next(s for s in r['states'] if s['job_id'] == scratch)
                      for original, scratch in r['job_mapping'].items()} for v, r in by_variant.items()}
    if len(mapped) == 2 and set(mapped['separate']) != set(mapped['combined']):
        raise CommandError('Comparison requires the same posting set.')
    lines = ['# Fit and requirements review', '', 'Private data. Owner labels are pending; schema validity is not quality evidence.',
             'No production default changed. Retain separate pending matched measurements and owner quality labels.', '',
             '| Metric | separate | combined |', '| --- | --- | --- |']
    for label, metric in [('Requests', lambda r: len(r['requests'])), ('Elapsed seconds', lambda r: r['ended']-r['started']),
                          ('Failures', lambda r: sum(bool(s.get('reason')) for s in r['states'])),
                          ('Repairs', lambda r: sum(q['repair'] for q in r['requests']))]:
        lines.append('| ' + label + ' | ' + ' | '.join(str(metric(by_variant[v])) if v in by_variant else 'Not measured' for v in ('separate', 'combined')) + ' |')
    for original in sorted({k for rows in mapped.values() for k in rows}):
        lines += ['', f'## Job {original}', '', '| separate | combined |', '| --- | --- |']
        cells = []
        for variant in ('separate', 'combined'):
            row = mapped.get(variant, {}).get(original)
            if row is None:
                cells.append('Not measured; pair the two results with benchmark_fit_review.')
                continue
            fit = row['fit'] or {}
            concise = {k: fit.get(k) for k in ('recommendation', 'fit_score', 'summary', 'risk_notes', 'missing_parts')}
            concise.update(skip=row.get('skip'), posting=row.get('posting'), requirements=row['requirements'],
                           reused=row.get('requirements_reused'), reason=row['reason'], elapsed_seconds=row['elapsed_seconds'],
                           requests=len(row['requests']), failures=sum(q['status']=='error' for q in row['requests']),
                           repairs=sum(q['repair'] for q in row['requests']))
            cells.append(json.dumps(concise, ensure_ascii=False).replace('|', '&#124;').replace('<', '&lt;').replace('>', '&gt;'))
        lines += ['| ' + ' | '.join(cells) + ' |', '', 'Owner label: pending. Check fit/skip, quoted language and letter instructions, ambiguity and missing posting handling.']
    (Path(output) / 'review.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')


run.write_review = write_review  # TASK-368: optional harness report hook, no production caller.
