from jobradar.models import ApplicationNote, FollowUp, JobEvaluation, JobLead
from jobradar.services.access import job_create_defaults
from jobradar.services.cleaning import clean_job_location
from jobradar.serializers import normalize_job_url


REPLACE_FIELDS = {
    'company': 'Unknown company',
    'title': 'Untitled role',
    'location': '',
    'url': '',
    'source': '',
    'raw_description': '',
    'submitted_by': '',
    'submitter_reason': '',
    'salary_info': '',
    'language_requirements': '',
    'work_mode': 'unknown',
    'status': 'new',
    'status_date': None,
    'interview_stage': None,
    'interview_total': None,
    'last_update_date': None,
    'feedback_due_date': None,
}


def _has(data, key):
    try:
        return key in data
    except TypeError:
        return False


def _get(data, key, default=None):
    try:
        return data.get(key, default)
    except AttributeError:
        return default


def replace_job_with_supplied_data(job, data, user=None, clear_related=True):
    """Replace an existing duplicate with only the newly supplied listing data.

    This intentionally clears stale enrichment/evaluation/status information so a
    link-only override becomes a fresh, unanalyzed listing again.
    """
    ownership = job_create_defaults(user) if user is not None else {}
    changed=[]
    candidate=next((text for text in (_get(data, 'original_source_text'),_get(data, 'raw_description')) if JobLead.is_meaningful_source(text)), '')
    if candidate and not JobLead.is_meaningful_source(job.original_source_text):
        job.original_source_text=candidate
        changed.append('original_source_text')
    for field, default in REPLACE_FIELDS.items():
        value = _get(data, field, default) if _has(data, field) else default
        if value in (None, '') and field in ('company', 'title', 'work_mode'):
            value = default
        if field == 'url':
            value = normalize_job_url(value or '')
        elif field == 'location':
            value = clean_job_location(value or '')
        elif field == 'work_mode' and value not in ['onsite', 'hybrid', 'remote', 'unknown']:
            value = 'unknown'
        if getattr(job, field) != value:
            setattr(job, field, value)
            changed.append(field)
    for field, value in ownership.items():
        if getattr(job, field, None) != value:
            setattr(job, field, value)
            changed.append(field)
    job.save()
    if clear_related:
        JobEvaluation.objects.filter(job=job).delete()
        ApplicationNote.objects.filter(job=job).delete()
        FollowUp.objects.filter(job=job).delete()
    return sorted(set(changed))
