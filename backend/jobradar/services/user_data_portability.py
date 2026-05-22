import json
from collections import defaultdict
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from jobradar.models import ApplicationNote, FollowUp, JobEvaluation, JobLead, UserProfile

SCHEMA_VERSION = 1
APP_NAME = 'dachapply'

JOB_FIELDS = ['company','title','location','url','source','raw_description','submitted_by','submitter_reason','salary_info','language_requirements','work_mode','status','status_date','interview_stage','interview_total','last_update_date','feedback_due_date']
EVALUATION_FIELDS = ['fit_score','priority','recommendation','summary','main_match_reasons','main_gaps','required_skills','nice_to_have_skills','matched_skills','missing_skills','cv_adjustment_notes','interview_prep_notes','risk_notes','next_action','structured_json_raw']
NOTE_FIELDS = ['note','note_type']
FOLLOWUP_FIELDS = ['follow_up_date','reason','completed']
PROFILE_FIELDS = []

# InviteCode is intentionally excluded: ownership is ambiguous and codes can act as
# access credentials/secrets. Django auth/session/admin/permission/token models are
# also excluded because exports must never contain passwords, sessions, tokens, logs,
# permissions, or secrets.

def _iso(value):
    return value.isoformat() if hasattr(value, 'isoformat') else value

def _clean_record(obj, fields, extra=None):
    data = {'id': obj.id}
    for field in fields:
        data[field] = _iso(getattr(obj, field))
    if extra:
        data.update(extra)
    return data

def owned_jobs(user):
    return JobLead.objects.filter(Q(created_by=user) | Q(submitted_for=user)).distinct()

def build_user_export(user):
    jobs = owned_jobs(user).prefetch_related('evaluations', 'notes', 'followups')
    job_ids = list(jobs.values_list('id', flat=True))
    profile = getattr(user, 'jobradar_profile', None)
    return {
        'schema_version': SCHEMA_VERSION,
        'exported_at': timezone.now().isoformat(),
        'app': APP_NAME,
        'user': {'id': user.id, 'username': user.get_username(), 'email': getattr(user, 'email', '') or ''},
        'data': {
            'profile': [_clean_record(profile, PROFILE_FIELDS)] if profile else [],
            'jobs': [_clean_record(j, JOB_FIELDS, {'created_by_username': j.created_by.username if j.created_by else '', 'submitted_for_username': j.submitted_for.username if j.submitted_for else ''}) for j in jobs],
            'evaluations': [_clean_record(e, EVALUATION_FIELDS, {'job': e.job_id}) for e in JobEvaluation.objects.filter(job_id__in=job_ids)],
            'notes': [_clean_record(n, NOTE_FIELDS, {'job': n.job_id}) for n in ApplicationNote.objects.filter(job_id__in=job_ids)],
            'followups': [_clean_record(f, FOLLOWUP_FIELDS, {'job': f.job_id}) for f in FollowUp.objects.filter(job_id__in=job_ids)],
        },
    }

def parse_import_payload(request):
    raw = request.body.decode('utf-8') if request.body else ''
    try:
        parsed = json.loads(raw) if raw else request.data
    except json.JSONDecodeError as exc:
        raise ValueError(f'Invalid JSON: {exc.msg}')
    if isinstance(parsed, dict) and isinstance(parsed.get('json'), str):
        try:
            parsed = json.loads(parsed['json'])
        except json.JSONDecodeError as exc:
            raise ValueError(f'Invalid JSON: {exc.msg}')
    return parsed

def _parse_value(field, value):
    if value in ('', None):
        return None if field.endswith('_date') else value
    if field.endswith('_date'):
        return parse_date(value) if isinstance(value, str) else value
    return value

def _assign_fields(obj, fields, data):
    changed = False
    for field in fields:
        if field not in data:
            continue
        value = _parse_value(field, data[field])
        if getattr(obj, field) != value:
            setattr(obj, field, value)
            changed = True
    return changed

def _find_owned_by_import_id(model, old_id, user, job_map=None):
    if not old_id:
        return None
    if model is JobLead:
        return owned_jobs(user).filter(id=old_id).first()
    if model is JobEvaluation:
        return model.objects.filter(id=old_id, job__in=owned_jobs(user)).first()
    if model is ApplicationNote:
        return model.objects.filter(id=old_id, job__in=owned_jobs(user)).first()
    if model is FollowUp:
        return model.objects.filter(id=old_id, job__in=owned_jobs(user)).first()
    return None

def import_user_export(user, payload):
    if not isinstance(payload, dict):
        return {'created': {}, 'updated': {}, 'skipped': {}, 'errors': ['Import payload must be a JSON object']}
    if payload.get('schema_version') != SCHEMA_VERSION:
        return {'created': {}, 'updated': {}, 'skipped': {}, 'errors': ['Unsupported schema_version']}
    if payload.get('app') != APP_NAME or not isinstance(payload.get('data'), dict):
        return {'created': {}, 'updated': {}, 'skipped': {}, 'errors': ['Invalid export structure']}

    summary = {'created': defaultdict(int), 'updated': defaultdict(int), 'skipped': defaultdict(int), 'errors': []}
    data = payload['data']
    job_map = {}

    with transaction.atomic():
        for item in data.get('profile', []):
            profile, created = UserProfile.objects.get_or_create(user=user)
            summary['created' if created else 'skipped']['profile'] += 1

        for item in data.get('jobs', []):
            if not isinstance(item, dict):
                summary['errors'].append('Skipped invalid job record')
                continue
            obj = _find_owned_by_import_id(JobLead, item.get('id'), user)
            if obj:
                changed = _assign_fields(obj, JOB_FIELDS, item)
                obj.created_by = user
                obj.submitted_for = None
                if changed:
                    obj.save()
                    summary['updated']['jobs'] += 1
                else:
                    obj.save(update_fields=['created_by','submitted_for'])
                    summary['skipped']['jobs'] += 1
            else:
                obj = JobLead(created_by=user, submitted_for=None)
                _assign_fields(obj, JOB_FIELDS, item)
                obj.company = obj.company or 'Unknown company'
                obj.title = obj.title or 'Untitled role'
                obj.save()
                summary['created']['jobs'] += 1
            if item.get('id'):
                job_map[item['id']] = obj

        for resource, model, fields in [('evaluations', JobEvaluation, EVALUATION_FIELDS), ('notes', ApplicationNote, NOTE_FIELDS), ('followups', FollowUp, FOLLOWUP_FIELDS)]:
            for item in data.get(resource, []):
                if not isinstance(item, dict):
                    summary['errors'].append(f'Skipped invalid {resource} record')
                    continue
                job = job_map.get(item.get('job')) or owned_jobs(user).filter(id=item.get('job')).first()
                if not job:
                    summary['skipped'][resource] += 1
                    continue
                obj = _find_owned_by_import_id(model, item.get('id'), user)
                if obj:
                    changed = _assign_fields(obj, fields, item)
                    if resource == 'notes':
                        obj.created_by = user
                    obj.job = job
                    if changed:
                        obj.save()
                        summary['updated'][resource] += 1
                    else:
                        obj.save()
                        summary['skipped'][resource] += 1
                else:
                    kwargs = {'job': job}
                    if resource == 'notes':
                        kwargs['created_by'] = user
                    obj = model(**kwargs)
                    _assign_fields(obj, fields, item)
                    obj.save()
                    summary['created'][resource] += 1

    return {k: dict(v) if hasattr(v, 'items') else v for k, v in summary.items()}
