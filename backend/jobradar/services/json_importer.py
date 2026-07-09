import json
import re
from urllib.parse import urlsplit, urlunsplit
from django.db import transaction
from django.db.models import Q
from jobradar.models import JobLead, JobEvaluation, ApplicationNote
from jobradar.services.access import accessible_jobs, job_create_defaults
from jobradar.services.cleaning import clean_job_location
from jobradar.services.job_replace import replace_job_with_supplied_data
from jobradar.services.demo_data import is_demo_job_payload, is_demo_user
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
    if 'location' in rec: rec['location']=clean_job_location(rec.get('location'))
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


def duplicate_title(title, queryset=None):
    base=title or 'Untitled role'
    qs=queryset if queryset is not None else JobLead.objects.all()
    n=1
    candidate=f'{base} ({n})'
    while qs.filter(title=candidate).exists():
        n+=1; candidate=f'{base} ({n})'
    return candidate


def duplicate_url_variants(url):
    url=normalize_job_url(url)
    if not url: return set()
    variants={url, url.rstrip('/')}
    if not url.endswith('/'): variants.add(url + '/')
    return {v for v in variants if v}


def duplicate_text(value):
    return re.sub(r'\s+', ' ', clean_label_text(value).casefold()).strip()


def position_duplicate_key(rec):
    company=duplicate_text(rec.get('company'))
    title=duplicate_text(rec.get('title'))
    if not company or not title: return None
    if company == 'unknown company' or title == 'untitled role': return None
    return ('position', company, title)


def duplicate_keys(rec):
    keys=[]
    url=normalize_job_url(rec.get('url'))
    if url: keys.append(('url', url.rstrip('/')))
    pos=position_duplicate_key(rec)
    if pos: keys.append(pos)
    return keys


def duplicate_jobs_qs(rec, queryset):
    query=None
    variants=duplicate_url_variants(rec.get('url'))
    if variants:
        query=Q(url__in=variants)
    pos=position_duplicate_key(rec)
    if pos:
        company=(rec.get('company') or '').strip()
        title=(rec.get('title') or '').strip()
        pos_query=Q(company__iexact=company, title__iexact=title)
        query=pos_query if query is None else query | pos_query
    if query is None:
        return queryset.none()
    return queryset.filter(query).distinct()


def action_for_duplicate(data, index):
    for a in data.get('duplicate_actions') or []:
        if a.get('index') == index: return a
    strategy=data.get('duplicate_strategy')
    return {'index': index, 'action': strategy} if strategy else None


def import_jobs_data(data, user=None):
    owned_qs=accessible_jobs(user) if user is not None else JobLead.objects.all()
    errors=[]; records=data.get('job_updates') or data.get('jobs') or data.get('job_details') or data.get('new_jobs')
    if not isinstance(records, list): return {'ok':False,'errors':['Root must contain jobs, new_jobs, or job_updates list']}
    records=[clean_job_record(rec) for rec in records]
    conflicts=[]; eval_conflicts=[]
    seen_keys={}
    auto_skips={}
    for i, rec in enumerate(records):
        dup_action=action_for_duplicate(data, i)
        if not rec.get('job_id') and not dup_action:
            matched_key=next((key for key in duplicate_keys(rec) if key in seen_keys), None)
            if matched_key:
                auto_skips[i]={'job_id':None,'action':'skipped_duplicate','duplicate_of_index':seen_keys[matched_key],'updated_fields':[]}
            else:
                for key in duplicate_keys(rec): seen_keys[key]=i
        if rec.get('job_id') and isinstance(rec.get('evaluation'), dict) and JobEvaluation.objects.filter(job_id=rec['job_id'], job__in=owned_qs).exists() and not action_for_duplicate(data, i) and not data.get('evaluation_strategy'):
            eval_conflicts.append({'index':i,'job_id':rec['job_id'],'incoming':{'company':rec.get('company'),'title':rec.get('title')},'existing_evaluations':list(JobEvaluation.objects.filter(job_id=rec['job_id'], job__in=owned_qs).values('id','fit_score','priority','recommendation','created_at')[:10])})
        if not rec.get('job_id') and i not in auto_skips:
            existing=list(duplicate_jobs_qs(rec, owned_qs).values('id','company','title','url','status')[:10])
            if existing and not dup_action:
                conflict={'index':i,'incoming':{'company':rec.get('company') or 'Unknown company','title':rec.get('title') or 'Untitled role'},'existing_jobs':existing}
                if rec.get('url'): conflict['url']=rec['url']
                conflicts.append(conflict)
        if rec.get('job_id') and not owned_qs.filter(id=rec['job_id']).exists(): errors.append(f'jobs[{i}].job_id does not exist: {rec["job_id"]}')
        if rec.get('work_mode') and rec.get('work_mode') not in ['onsite','hybrid','remote','unknown']: errors.append(f'jobs[{i}].work_mode invalid')
        if user is not None and not is_demo_user(user) and is_demo_job_payload(rec.get('url'), rec.get('source')): errors.append(f'jobs[{i}] demo jobs are only available in the demo account')
        if not rec.get('job_id') and not (rec.get('url') or rec.get('raw_description') or rec.get('company') or rec.get('title')): errors.append(f'jobs[{i}] needs at least url, description, company, or title')
        if isinstance(rec.get('evaluation'), dict): errors += validate_eval(rec['evaluation'], i, require_job_id=False)
    if conflicts: return {'ok':False,'type':'duplicate_conflicts','message':'Some jobs already exist. Choose override, duplicate, skip, or abort.','conflicts':conflicts}
    if eval_conflicts: return {'ok':False,'type':'evaluation_conflicts','message':'These jobs already have evaluations. Choose override, duplicate, skip, or abort.','conflicts':eval_conflicts}
    if errors: return {'ok':False,'errors':errors}
    results=[]; eval_ids=[]
    with transaction.atomic():
        for i, rec in enumerate(records):
            dup_action=action_for_duplicate(data, i)
            if i in auto_skips:
                results.append(auto_skips[i]); continue
            if rec.get('job_id'):
                job=owned_qs.get(id=rec['job_id']); action='updated'; changed=[]
                for f in JOB_UPDATE_FIELDS:
                    val=normalize_job_url(rec.get(f)) if f=='url' else clean_job_location(rec.get(f)) if f=='location' else rec.get(f)
                    if val is not None and val != '': setattr(job, f, val); changed.append(f)
                job.save()
            elif dup_action and dup_action.get('action') == 'skip':
                results.append({'job_id':None,'action':'skipped_duplicate','updated_fields':[]}); continue
            elif dup_action and dup_action.get('action') == 'override':
                existing_qs=duplicate_jobs_qs(rec, owned_qs)
                job=owned_qs.filter(id=dup_action.get('existing_job_id')).first() if dup_action.get('existing_job_id') else existing_qs.first()
                if job:
                    action='overridden'; changed=replace_job_with_supplied_data(job, rec, user)
                else:
                    title=rec.get('title') or 'Untitled role'
                    create_defaults=job_create_defaults(user) if user is not None else {}
                    source=create_defaults.pop('source', rec.get('source','bulk_links'))
                    job=JobLead.objects.create(company=rec.get('company') or 'Unknown company', title=title, location=rec.get('location',''), url=normalize_job_url(rec.get('url','')), source=source, raw_description=rec.get('raw_description',''), salary_info=rec.get('salary_info',''), language_requirements=rec.get('language_requirements',''), work_mode=rec.get('work_mode') or 'unknown', **create_defaults)
                    action='created'; changed=sorted(JOB_UPDATE_FIELDS)
            else:
                title=rec.get('title') or 'Untitled role'
                if dup_action and dup_action.get('action') == 'duplicate': title=duplicate_title(title, owned_qs)
                create_defaults=job_create_defaults(user) if user is not None else {}
                source=create_defaults.pop('source', rec.get('source','bulk_links'))
                job=JobLead.objects.create(company=rec.get('company') or 'Unknown company', title=title, location=rec.get('location',''), url=normalize_job_url(rec.get('url','')), source=source, raw_description=rec.get('raw_description',''), salary_info=rec.get('salary_info',''), language_requirements=rec.get('language_requirements',''), work_mode=rec.get('work_mode') or 'unknown', **create_defaults)
                action='created_duplicate' if dup_action and dup_action.get('action') == 'duplicate' else 'created'; changed=sorted(JOB_UPDATE_FIELDS)
            note=rec.get('notes') or rec.get('note') or rec.get('uncertainty')
            if note: ApplicationNote.objects.create(job=job, note=str(note), note_type='general', created_by=user if user is not None else None)
            if isinstance(rec.get('evaluation'), dict):
                ev_action=(action_for_duplicate(data, i) or {}).get('action') or data.get('evaluation_strategy')
                if ev_action == 'skip': pass
                else:
                    if ev_action == 'override': JobEvaluation.objects.filter(job=job).delete()
                    eval_ids.append(create_evaluation(job, rec['evaluation']).id)
            results.append({'job_id':job.id,'company':job.company,'title':job.title,'action':action,'updated_fields':sorted(changed)})
    imported_jobs=[r for r in results if r.get('job_id')]
    return {'ok':True,'type':'jobs','jobs':results,'imported_jobs':imported_jobs,'evaluation_ids':eval_ids,'count':len(results),'jobs_found':len(imported_jobs)}


def import_any_json(pasted, user=None):
    try: data=json.loads(pasted) if isinstance(pasted, str) else pasted
    except json.JSONDecodeError as e: return {'ok':False,'errors':[f'Invalid JSON: {e}']}
    if not isinstance(data, dict): return {'ok':False,'errors':['Root must be a JSON object']}
    if any(k in data for k in ['job_updates','jobs','job_details','new_jobs']): return import_jobs_data(data, user=user)
    return import_evaluations(data, user=user)


def import_evaluations(pasted, user=None):
    if isinstance(pasted, str):
        try: data=json.loads(pasted)
        except json.JSONDecodeError as e: return {'ok':False,'errors':[f'Invalid JSON: {e}']}
    else: data=pasted
    errors=[]
    if not isinstance(data, dict) or not isinstance(data.get('evaluations'), list): errors.append('Root must contain evaluations list')
    if errors: return {'ok':False,'errors':errors}
    owned_qs=accessible_jobs(user) if user is not None else JobLead.objects.all()
    created=[]
    for i, ev in enumerate(data['evaluations']):
        errors += validate_eval(ev, i, require_job_id=True)
        if 'job_id' in ev and not owned_qs.filter(id=ev['job_id']).exists(): errors.append(f'evaluation[{i}].job_id does not exist: {ev["job_id"]}')
    if errors: return {'ok':False,'errors':errors}
    with transaction.atomic():
        for ev in data['evaluations']:
            job=owned_qs.get(id=ev['job_id']); created.append(create_evaluation(job, ev).id)
    return {'ok':True,'created_ids':created,'count':len(created)}
