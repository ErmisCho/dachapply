import json
from django.db import transaction
from jobradar.models import JobLead, JobEvaluation, ApplicationNote
from rest_framework import serializers

REQ={'job_id', 'company', 'title', 'fit_score', 'priority', 'recommendation', 'summary', 'main_match_reasons', 'main_gaps', 'required_skills', 'nice_to_have_skills', 'matched_skills', 'missing_skills', 'cv_adjustment_notes', 'interview_prep_notes', 'risk_notes', 'next_action'}
EVAL_REQ_NO_JOB=REQ-{'job_id','company','title'}
LIST_FIELDS=['main_match_reasons','main_gaps','required_skills','nice_to_have_skills','matched_skills','missing_skills']
JOB_UPDATE_FIELDS={'company','title','location','url','source','raw_description','salary_info','language_requirements','work_mode'}


def normalize_job_url(value):
    value=(value or '').strip()
    if not value: return ''
    if value.startswith('http://') or value.startswith('https://'): return value
    if value.startswith('https-') or value.startswith('http-'):
        scheme, rest=value.split('-', 1); parts=rest.split('-')
        if len(parts) >= 2 and '.' in parts[0]: return f'{scheme}://' + parts[0] + '/' + '/'.join(parts[1:])
    if '.' in value and ' ' not in value: return 'https://' + value
    return value


def value_is_valid_url(value):
    value=normalize_job_url(value)
    if not value: return False
    try:
        serializers.URLField(max_length=1000).run_validation(value)
        return True
    except serializers.ValidationError:
        return False


def clean_job_record(rec):
    rec=dict(rec)
    if not rec.get('url') and value_is_valid_url(rec.get('company')):
        rec['url']=normalize_job_url(rec.get('company'))
        rec['company']=''
    if rec.get('url'):
        rec['url']=normalize_job_url(rec.get('url'))
    return rec


def validate_eval(ev, i, require_job_id=True):
    errors=[]; required=REQ if require_job_id else EVAL_REQ_NO_JOB
    missing=required-set(ev.keys())
    if missing: errors.append(f'evaluation[{i}] missing: {", ".join(sorted(missing))}')
    if ev.get('priority') not in ['high','medium','low']: errors.append(f'evaluation[{i}].priority invalid')
    if ev.get('recommendation') not in ['apply','maybe','skip']: errors.append(f'evaluation[{i}].recommendation invalid')
    if not isinstance(ev.get('fit_score'), int) or not 0 <= ev.get('fit_score', -1) <= 100: errors.append(f'evaluation[{i}].fit_score must be integer 0..100')
    for f in LIST_FIELDS:
        if f in ev and not isinstance(ev[f], list): errors.append(f'evaluation[{i}].{f} must be list')
    return errors


def create_evaluation(job, ev):
    return JobEvaluation.objects.create(
        job=job, fit_score=ev['fit_score'], priority=ev['priority'], recommendation=ev['recommendation'], summary=ev.get('summary',''),
        main_match_reasons=ev.get('main_match_reasons',[]), main_gaps=ev.get('main_gaps',[]), required_skills=ev.get('required_skills',[]), nice_to_have_skills=ev.get('nice_to_have_skills',[]),
        matched_skills=ev.get('matched_skills',[]), missing_skills=ev.get('missing_skills',[]), cv_adjustment_notes=ev.get('cv_adjustment_notes',''), interview_prep_notes=ev.get('interview_prep_notes',''),
        risk_notes=ev.get('risk_notes',''), next_action=ev.get('next_action',''), structured_json_raw=ev)


def import_jobs_data(data):
    errors=[]; records=data.get('job_updates') or data.get('jobs') or data.get('job_details') or data.get('new_jobs')
    if not isinstance(records, list): return {'ok':False,'errors':['Root must contain jobs, new_jobs, or job_updates list']}
    records=[clean_job_record(rec) for rec in records]
    for i, rec in enumerate(records):
        if rec.get('job_id') and not JobLead.objects.filter(id=rec['job_id']).exists(): errors.append(f'jobs[{i}].job_id does not exist: {rec["job_id"]}')
        if rec.get('work_mode') and rec.get('work_mode') not in ['onsite','hybrid','remote','unknown']: errors.append(f'jobs[{i}].work_mode invalid')
        if not rec.get('job_id') and not (rec.get('url') or rec.get('raw_description') or rec.get('company') or rec.get('title')): errors.append(f'jobs[{i}] needs at least url, description, company, or title')
        if isinstance(rec.get('evaluation'), dict): errors += validate_eval(rec['evaluation'], i, require_job_id=False)
    if errors: return {'ok':False,'errors':errors}
    results=[]; eval_ids=[]
    with transaction.atomic():
        for rec in records:
            if rec.get('job_id'):
                job=JobLead.objects.get(id=rec['job_id']); action='updated'; changed=[]
                for f in JOB_UPDATE_FIELDS:
                    val=normalize_job_url(rec.get(f)) if f=='url' else rec.get(f)
                    if val is not None and val != '': setattr(job, f, val); changed.append(f)
                job.save()
            else:
                job=JobLead.objects.create(company=rec.get('company') or 'Unknown company', title=rec.get('title') or 'Untitled role', location=rec.get('location',''), url=normalize_job_url(rec.get('url','')), source=rec.get('source','bulk_links'), raw_description=rec.get('raw_description',''), salary_info=rec.get('salary_info',''), language_requirements=rec.get('language_requirements',''), work_mode=rec.get('work_mode') or 'unknown')
                action='created'; changed=sorted(JOB_UPDATE_FIELDS)
            note=rec.get('notes') or rec.get('note') or rec.get('uncertainty')
            if note: ApplicationNote.objects.create(job=job, note=str(note), note_type='general')
            if isinstance(rec.get('evaluation'), dict): eval_ids.append(create_evaluation(job, rec['evaluation']).id)
            results.append({'job_id':job.id,'action':action,'updated_fields':sorted(changed)})
    return {'ok':True,'type':'jobs','jobs':results,'evaluation_ids':eval_ids,'count':len(results)}


def import_any_json(pasted):
    try: data=json.loads(pasted) if isinstance(pasted, str) else pasted
    except json.JSONDecodeError as e: return {'ok':False,'errors':[f'Invalid JSON: {e}']}
    if not isinstance(data, dict): return {'ok':False,'errors':['Root must be a JSON object']}
    if any(k in data for k in ['job_updates','jobs','job_details','new_jobs']): return import_jobs_data(data)
    return import_evaluations(data)


def import_evaluations(pasted):
    if isinstance(pasted, str):
        try: data=json.loads(pasted)
        except json.JSONDecodeError as e: return {'ok':False,'errors':[f'Invalid JSON: {e}']}
    else: data=pasted
    errors=[]
    if not isinstance(data, dict) or not isinstance(data.get('evaluations'), list): errors.append('Root must contain evaluations list')
    if errors: return {'ok':False,'errors':errors}
    created=[]
    for i, ev in enumerate(data['evaluations']):
        errors += validate_eval(ev, i, require_job_id=True)
        if 'job_id' in ev and not JobLead.objects.filter(id=ev['job_id']).exists(): errors.append(f'evaluation[{i}].job_id does not exist: {ev["job_id"]}')
    if errors: return {'ok':False,'errors':errors}
    with transaction.atomic():
        for ev in data['evaluations']:
            job=JobLead.objects.get(id=ev['job_id']); created.append(create_evaluation(job, ev).id)
    return {'ok':True,'created_ids':created,'count':len(created)}
