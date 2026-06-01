import json
import re
from urllib.parse import urlsplit, urlunsplit
from django.db import transaction
from jobradar.models import JobLead, JobEvaluation, ApplicationNote
from rest_framework import serializers

REQ={'job_id', 'company', 'title', 'fit_score', 'priority', 'recommendation', 'summary', 'main_match_reasons', 'main_gaps', 'required_skills', 'nice_to_have_skills', 'matched_skills', 'missing_skills', 'cv_adjustment_notes', 'interview_prep_notes', 'risk_notes', 'next_action'}
EVAL_REQ_NO_JOB=REQ-{'job_id','company','title'}
LIST_FIELDS=['main_match_reasons','main_gaps','required_skills','nice_to_have_skills','matched_skills','missing_skills']
JOB_UPDATE_FIELDS={'company','title','location','url','source','raw_description','salary_info','language_requirements','work_mode'}


def normalize_job_url(value):
    raw=(value or '').strip()
    value=raw.replace('https://[https://','https://').replace('http://[http://','http://').strip('[]()<>.,;')
    embedded=re.findall(r'https?://[^\s\[\])>"}]+', value)
    if embedded: value=embedded[-1].strip('[]()<>.,;')
    if not value: return ''
    if value.startswith('http://') or value.startswith('https://'):
        parts=urlsplit(value)
        return urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip('/'), '', ''))
    if value.startswith('https-') or value.startswith('http-'):
        scheme, rest=value.split('-', 1); parts=rest.split('-')
        if len(parts) >= 2 and '.' in parts[0]: return f'{scheme}://' + parts[0] + '/' + '/'.join(parts[1:])
    if '.' in value and ' ' not in value: return 'https://' + value
    return value


def value_is_valid_url(value):
    raw=str(value or '').strip()
    if '](' in raw or (' ' in raw and not raw.startswith(('http://','https://','http-','https-'))): return False
    value=normalize_job_url(raw)
    if not value: return False
    try:
        serializers.URLField(max_length=1000).run_validation(value)
        return True
    except serializers.ValidationError:
        return False


def extract_url_from_text(value):
    text=str(value or '')
    m=re.search(r'https?://[^\s)\]]+', text)
    if not m: return ''
    url=m.group(0).split('%22')[0].split('"')[0].rstrip('.,;')
    return normalize_job_url(url)


def clean_label_text(value):
    text=str(value or '').strip()
    if not text: return ''
    # Fix ChatGPT/markdown accidents like:
    # Enlivion](https://www.karriere.at/jobs/10019854%22,%22company%22:%22Enlivion) GmbH
    if '](' in text:
        before=text.split('](',1)[0].lstrip('[').strip()
        suffix=''
        if ')' in text:
            suffix=text.split(')',1)[1].strip()
        text=(before + (' ' + suffix if suffix else '')).strip()
    text=re.sub(r'https?://[^\s)\]]+', '', text)
    text=text.replace('[','').replace(']','').replace('(','').replace(')','')
    text=text.replace('%22','').replace('"','').replace('company:', '').replace('title:', '')
    text=re.sub(r'\s+', ' ', text).strip(' ,;:-')
    return text


def clean_job_title(value):
    text=clean_label_text(value)
    text=re.sub(r'\s*[-–—,;:]*\s*\(?\s*[mwfdx](?:\s*/\s*[mwfdx]){1,3}\s*\)?\s*$', '', text, flags=re.IGNORECASE)
    return re.sub(r'\s+', ' ', text).strip(' ,;:-')


def clean_job_record(rec):
    rec=dict(rec)
    embedded_url=extract_url_from_text(rec.get('url')) or extract_url_from_text(rec.get('company')) or extract_url_from_text(rec.get('title'))
    if embedded_url and not rec.get('url'):
        rec['url']=embedded_url
    if rec.get('url'):
        rec['url']=normalize_job_url(extract_url_from_text(rec.get('url')) or rec.get('url'))
    if value_is_valid_url(rec.get('company')):
        if not rec.get('url'): rec['url']=normalize_job_url(rec.get('company'))
        rec['company']=''
    if value_is_valid_url(rec.get('title')):
        if not rec.get('url'): rec['url']=normalize_job_url(rec.get('title'))
        rec['title']=''
    if 'company' in rec: rec['company']=clean_label_text(rec.get('company'))
    if 'title' in rec: rec['title']=clean_job_title(rec.get('title'))
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


def duplicate_title(title):
    base=title or 'Untitled role'
    n=1
    candidate=f'{base} ({n})'
    while JobLead.objects.filter(title=candidate).exists():
        n+=1; candidate=f'{base} ({n})'
    return candidate


def action_for_duplicate(data, index):
    for a in data.get('duplicate_actions') or []:
        if a.get('index') == index: return a
    strategy=data.get('duplicate_strategy')
    return {'index': index, 'action': strategy} if strategy else None


def import_jobs_data(data):
    errors=[]; records=data.get('job_updates') or data.get('jobs') or data.get('job_details') or data.get('new_jobs')
    if not isinstance(records, list): return {'ok':False,'errors':['Root must contain jobs, new_jobs, or job_updates list']}
    records=[clean_job_record(rec) for rec in records]
    conflicts=[]; eval_conflicts=[]
    for i, rec in enumerate(records):
        if rec.get('job_id') and isinstance(rec.get('evaluation'), dict) and JobEvaluation.objects.filter(job_id=rec['job_id']).exists() and not action_for_duplicate(data, i) and not data.get('evaluation_strategy'):
            eval_conflicts.append({'index':i,'job_id':rec['job_id'],'incoming':{'company':rec.get('company'),'title':rec.get('title')},'existing_evaluations':list(JobEvaluation.objects.filter(job_id=rec['job_id']).values('id','fit_score','priority','recommendation','created_at')[:10])})
        if not rec.get('job_id') and rec.get('url'):
            existing=list(JobLead.objects.filter(url=rec['url']).values('id','company','title','url','status')[:10])
            if existing and not action_for_duplicate(data, i):
                conflicts.append({'index':i,'url':rec['url'],'incoming':{'company':rec.get('company') or 'Unknown company','title':rec.get('title') or 'Untitled role'},'existing_jobs':existing})
        if rec.get('job_id') and not JobLead.objects.filter(id=rec['job_id']).exists(): errors.append(f'jobs[{i}].job_id does not exist: {rec["job_id"]}')
        if rec.get('work_mode') and rec.get('work_mode') not in ['onsite','hybrid','remote','unknown']: errors.append(f'jobs[{i}].work_mode invalid')
        if not rec.get('job_id') and not (rec.get('url') or rec.get('raw_description') or rec.get('company') or rec.get('title')): errors.append(f'jobs[{i}] needs at least url, description, company, or title')
        if isinstance(rec.get('evaluation'), dict): errors += validate_eval(rec['evaluation'], i, require_job_id=False)
    if conflicts: return {'ok':False,'type':'duplicate_conflicts','message':'Some jobs already exist. Choose override, duplicate, skip, or abort.','conflicts':conflicts}
    if eval_conflicts: return {'ok':False,'type':'evaluation_conflicts','message':'These jobs already have evaluations. Choose override, duplicate, skip, or abort.','conflicts':eval_conflicts}
    if errors: return {'ok':False,'errors':errors}
    results=[]; eval_ids=[]
    with transaction.atomic():
        for i, rec in enumerate(records):
            dup_action=action_for_duplicate(data, i)
            if rec.get('job_id'):
                job=JobLead.objects.get(id=rec['job_id']); action='updated'; changed=[]
                for f in JOB_UPDATE_FIELDS:
                    val=normalize_job_url(rec.get(f)) if f=='url' else rec.get(f)
                    if val is not None and val != '': setattr(job, f, val); changed.append(f)
                job.save()
            elif dup_action and dup_action.get('action') == 'skip':
                results.append({'job_id':None,'action':'skipped_duplicate','updated_fields':[]}); continue
            elif dup_action and dup_action.get('action') == 'override':
                existing_qs=JobLead.objects.filter(url=rec.get('url'))
                job=JobLead.objects.filter(id=dup_action.get('existing_job_id')).first() if dup_action.get('existing_job_id') else existing_qs.first()
                action='overridden'; changed=[]
                for f in JOB_UPDATE_FIELDS:
                    val=normalize_job_url(rec.get(f)) if f=='url' else rec.get(f)
                    if val is not None and val != '': setattr(job, f, val); changed.append(f)
                job.save()
            else:
                title=rec.get('title') or 'Untitled role'
                if dup_action and dup_action.get('action') == 'duplicate': title=duplicate_title(title)
                job=JobLead.objects.create(company=rec.get('company') or 'Unknown company', title=title, location=rec.get('location',''), url=normalize_job_url(rec.get('url','')), source=rec.get('source','bulk_links'), raw_description=rec.get('raw_description',''), salary_info=rec.get('salary_info',''), language_requirements=rec.get('language_requirements',''), work_mode=rec.get('work_mode') or 'unknown')
                action='created_duplicate' if dup_action and dup_action.get('action') == 'duplicate' else 'created'; changed=sorted(JOB_UPDATE_FIELDS)
            note=rec.get('notes') or rec.get('note') or rec.get('uncertainty')
            if note: ApplicationNote.objects.create(job=job, note=str(note), note_type='general')
            if isinstance(rec.get('evaluation'), dict):
                ev_action=(action_for_duplicate(data, i) or {}).get('action') or data.get('evaluation_strategy')
                if ev_action == 'skip': pass
                else:
                    if ev_action == 'override': JobEvaluation.objects.filter(job=job).delete()
                    eval_ids.append(create_evaluation(job, rec['evaluation']).id)
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
