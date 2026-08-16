import json

from django.db import connection
from rest_framework.exceptions import APIException

from jobradar.models import UserProfile
from jobradar.services.cleaning import clean_job_location


class CandidateProfileRequired(APIException):
    """Refuse prompt generation rather than evaluate the job against nobody.

    There used to be a fallback here: an account with an empty profile silently borrowed one
    specific person's bio, so every fit score, gap list and recommendation it produced described
    a stranger. A placeholder would have the same defect -- the model still scores against it --
    so an empty profile refuses instead. `code` is stable for the frontend nudge.
    """
    status_code = 400

    def __init__(self):
        super().__init__({
            'code': 'candidate_profile_required',
            'detail': 'Add your candidate profile in Settings before generating a prompt. Prompts are scored against your profile, and an empty one would score every job against nobody.',
        })

RECOMMENDATION_RULES = '''Recommendation rules:
apply = realistic fit with acceptable gaps.
maybe = meaningful overlap but significant hiring risk or unclear role emphasis.
skip = low fit or role mostly targets gaps.'''

SKILL_ANALYSIS_RULES = '''Skill analysis rules:
Always analyze skills for every evaluated job.
Extract required_skills from hard requirements in the job description.
Extract nice_to_have_skills from preferred/bonus requirements.
matched_skills must only include skills supported by the candidate profile.
missing_skills must include hard requirements that are missing, weak, basic, learning-only, or only personal-project experience when professional experience is required.
Do not leave required_skills, matched_skills, or missing_skills empty unless the job description truly provides no skill signals.'''

EVALUATION_SCHEMA = '{"evaluations":[{"job_id":1,"company":"...","title":"...","fit_score":0,"priority":"high|medium|low","recommendation":"apply|maybe|skip","summary":"...","main_match_reasons":["..."],"main_gaps":["..."],"required_skills":["..."],"nice_to_have_skills":["..."],"matched_skills":["..."],"missing_skills":["..."],"cv_adjustment_notes":"...","interview_prep_notes":"...","risk_notes":"...","next_action":"..."}],"overall_ranking":[{"job_id":1,"rank":1,"reason":"..."}],"strategic_advice":"..."}'
COMBINED_SCHEMA = '{"jobs":[{"job_id":1,"url":"https://...","company":"...","title":"...","location":"...","source":"...","raw_description":"...","original_source_text":"complete original job text without truncation","salary_info":"...","language_requirements":"...","work_mode":"onsite|hybrid|remote|unknown","evaluation":{"fit_score":0,"priority":"high|medium|low","recommendation":"apply|maybe|skip","summary":"...","main_match_reasons":["..."],"main_gaps":["..."],"required_skills":["..."],"nice_to_have_skills":["..."],"matched_skills":["..."],"missing_skills":["..."],"cv_adjustment_notes":"...","interview_prep_notes":"...","risk_notes":"...","next_action":"..."}}],"strategic_advice":"..."}'
ENRICHMENT_SCHEMA = '{"job_updates":[{"job_id":1,"company":"...","title":"...","location":"...","url":"...","source":"...","raw_description":"...","original_source_text":"complete original job text without truncation","salary_info":"...","language_requirements":"...","work_mode":"onsite|hybrid|remote|unknown","notes":"any uncertainty or assumptions"}]}'
BULK_LINKS_SCHEMA = '{"jobs":[{"temp_id":"link_1","url":"https://...","company":"...","title":"...","location":"...","source":"...","raw_description":"...","original_source_text":"complete original job text without truncation","salary_info":"...","language_requirements":"...","work_mode":"onsite|hybrid|remote|unknown","evaluation":{"fit_score":0,"priority":"high|medium|low","recommendation":"apply|maybe|skip","summary":"...","main_match_reasons":["..."],"main_gaps":["..."],"required_skills":["..."],"nice_to_have_skills":["..."],"matched_skills":["..."],"missing_skills":["..."],"cv_adjustment_notes":"...","interview_prep_notes":"...","risk_notes":"...","next_action":"..."}}],"strategic_advice":"..."}'

DEFAULT_EVALUATION_PROMPT_TEMPLATE = '''Evaluate these DACH software engineering jobs against the candidate profile.
Be honest, direct, and do not invent experience. Consider DACH market fit, language requirements, target roles, preferred stack, selling points, red flags, and gaps described in the candidate profile.
Return one valid JSON object only. No markdown, code fences, citations, reference footnotes, or prose outside JSON. Escape double quotes and control characters inside every string value. Before replying, verify the complete response parses as JSON.

CANDIDATE PROFILE:
{candidate_profile}

{recommendation_rules}

{skill_analysis_rules}
{custom_instructions_section}
EXPECTED JSON SCHEMA:
{schema}

JOBS:
{jobs}'''

DEFAULT_COMBINED_PROMPT_TEMPLATE = '''For each existing job below, first fill missing/incorrect job details, then evaluate the job against the candidate profile.
Preserve job_id exactly. Open the job URL when available and copy the complete job posting verbatim, in its original language, into original_source_text. Never translate, summarize, rewrite, or truncate original_source_text. Put links only in url. Never put URLs in company or title. For location, use the city only when a city is known (for example Vienna, not AUT 1100 Vienna). Do not invent experience or facts; use unknown/empty values when needed.
Return one valid JSON object only. No markdown, code fences, citations, reference footnotes, or prose outside JSON. Escape double quotes and control characters inside every string value. Before replying, verify the complete response parses as JSON.

CANDIDATE PROFILE:
{candidate_profile}

{recommendation_rules}

{skill_analysis_rules}
{custom_instructions_section}
EXPECTED JSON SCHEMA:
{schema}

JOBS:
{jobs}'''

DEFAULT_ENRICHMENT_PROMPT_TEMPLATE = '''Extract missing structured job details from the provided job URLs/descriptions. Open the job URL when available and copy the complete job posting verbatim, in its original language, into original_source_text. Never translate, summarize, rewrite, or truncate original_source_text. Use only information visible in the text or URL context. If a detail is unknown, use an empty string or unknown. For location, use the city only when a city is known (for example Vienna, not AUT 1100 Vienna). Do not invent facts.
Use the candidate profile only as context for which job details are most relevant; do not evaluate unless the schema asks for it.
Return one valid JSON object only. No markdown, code fences, citations, reference footnotes, or prose outside JSON. Escape double quotes and control characters inside every string value. Before replying, verify the complete response parses as JSON.
For each job, preserve job_id exactly so the app can update the right record.

CANDIDATE PROFILE:
{candidate_profile}
{custom_instructions_section}
EXPECTED JSON SCHEMA:
{schema}

JOBS NEEDING DETAILS:
{jobs}'''

DEFAULT_BULK_LINKS_PROMPT_TEMPLATE = '''You will receive a list of job links. For each link, extract job details and evaluate the job against the candidate profile below.
Important: put the link only in the url field. Never put a URL in company or title. Company must be the employer name, or Unknown company if unknown. Title must be the position name, or Untitled role if unknown. For location, use the city only when a city is known (for example Vienna, not AUT 1100 Vienna).
Open each job URL when available. Copy the complete job posting verbatim, in its original language, into original_source_text. Never translate, summarize, rewrite, or truncate original_source_text. Use only information from the page, provided link text, and job description text supplied by the user. If you cannot access a page or a detail is unknown, use an empty string or unknown. Do not invent experience or facts.
Return one valid JSON object only. No markdown, code fences, citations, reference footnotes, or prose outside JSON. Escape double quotes and control characters inside every string value. Before replying, verify the complete response parses as JSON.

CANDIDATE PROFILE:
{candidate_profile}

{recommendation_rules}

{skill_analysis_rules}
{custom_instructions_section}
EXPECTED JSON SCHEMA:
{schema}

JOB LINKS:
{links}'''

PROFILE_FIELDS = [
    ('Candidate profile', 'candidate_profile'),
    ('Target roles', 'target_roles'),
    ('Preferred locations', 'preferred_locations'),
    ('Salary expectations', 'salary_expectations'),
    ('Language levels', 'language_levels'),
    ('Preferred stack', 'preferred_stack'),
    ('Red flags / avoid', 'red_flags'),
    ('Selling points', 'selling_points'),
]
PROFILE_FIELD_NAMES = [field for _, field in PROFILE_FIELDS]


def _db_json_checked_profile_fields():
    """Detect old/dev SQLite schemas where these profile columns were created
    with JSON_VALID checks. The model now treats them as text, but encoding to a
    JSON string keeps those drifted databases usable instead of raising 500s.
    """
    if connection.vendor != 'sqlite':
        return set()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='jobradar_userprofile'")
            row = cursor.fetchone()
    except Exception:
        return set()
    sql = row[0] if row else ''
    return {field for field in PROFILE_FIELD_NAMES if f'JSON_VALID("{field}")' in sql}


def decode_profile_value(value):
    if not isinstance(value, str):
        return value or ''
    stripped=value.strip()
    if len(stripped) >= 2 and stripped[0] == '"' and stripped[-1] == '"':
        try:
            decoded=json.loads(stripped)
            return decoded if isinstance(decoded, str) else value
        except json.JSONDecodeError:
            return value
    return value


def encode_profile_value(field, value):
    value = value or ''
    if field in _db_json_checked_profile_fields() and isinstance(value, str):
        return json.dumps(value)
    return value


def user_profile_settings(user):
    # No candidate_profile default and no backfill: an account with an empty profile keeps it
    # empty, so prompt generation refuses instead of borrowing somebody else's bio.
    defaults={field: encode_profile_value(field, '') for field in PROFILE_FIELD_NAMES}
    profile, _ = UserProfile.objects.get_or_create(user=user, defaults=defaults)
    return profile


def _profile_parts(profile):
    parts = []
    for label, field in PROFILE_FIELDS:
        value = (decode_profile_value(getattr(profile, field, '')) or '').strip()
        if value:
            parts.append(f'{label}:\n{value}')
    return parts


def build_candidate_profile_text(user):
    if not getattr(user, 'is_authenticated', False):
        return ''
    return '\n\n'.join(_profile_parts(user_profile_settings(user)))


def has_candidate_profile(user):
    """Whether this account has profile text of its own. Read-only: never creates a profile row.

    Deliberately queried rather than read off user.jobradar_profile: that relation is cached on the
    user instance, so a reused instance answers with the profile as it looked before the last save.
    """
    if not getattr(user, 'is_authenticated', False):
        return False
    profile = UserProfile.objects.filter(user=user).first()
    return bool(profile and _profile_parts(profile))


def _profile(candidate_profile=None):
    text = (candidate_profile or '').strip()
    if not text:
        raise CandidateProfileRequired
    return text


def _custom_instructions_section(custom_instructions):
    return f'\nCUSTOM INSTRUCTIONS:\n{custom_instructions}\n\n' if custom_instructions else '\n'


def _render_template(template, default_template, context):
    source=(template or '').strip() or default_template
    try:
        return source.format(**context).strip()
    except (KeyError, ValueError):
        # If a user edits literal JSON braces into the template without escaping
        # them, fall back to the safe default instead of returning a broken API.
        return default_template.format(**context).strip()


def default_prompt_templates():
    return {
        'evaluation_prompt_template': DEFAULT_EVALUATION_PROMPT_TEMPLATE,
        'combined_prompt_template': DEFAULT_COMBINED_PROMPT_TEMPLATE,
        'enrichment_prompt_template': DEFAULT_ENRICHMENT_PROMPT_TEMPLATE,
        'bulk_links_prompt_template': DEFAULT_BULK_LINKS_PROMPT_TEMPLATE,
    }


def _evaluation_jobs_block(jobs):
    lines=[]
    for j in jobs:
        desc=j.source_text or ''
        lines += [f'Job ID: {j.id}', f'Company: {j.company}', f'Title: {j.title}', f'Location: {clean_job_location(j.location)}', f'Work mode: {j.work_mode}', f'URL: {j.url}', f'Salary: {j.salary_info}', f'Language requirements: {j.language_requirements}', f'Description: {desc}', '---']
    return '\n'.join(lines)


def _combined_jobs_block(jobs):
    lines=[]
    for j in jobs:
        lines += [f'Job ID: {j.id}', f'Current company: {j.company}', f'Current title: {j.title}', f'URL: {j.url}', f'Location: {clean_job_location(j.location)}', f'Work mode: {j.work_mode}', f'Salary: {j.salary_info}', f'Languages: {j.language_requirements}', f'Description: {j.source_text or ""}', '---']
    return '\n'.join(lines)


def _enrichment_jobs_block(jobs):
    lines=[]
    for j in jobs:
        lines += [f'Job ID: {j.id}', f'Current company: {j.company}', f'Current title: {j.title}', f'URL: {j.url}', f'Current location: {clean_job_location(j.location)}', f'Current description: {j.source_text or ""}', '---']
    return '\n'.join(lines)


def build_bulk_links_prompt(links, custom_instructions='', candidate_profile=None, prompt_template=None):
    links_block='\n'.join(f'link_{i}: {link}' for i, link in enumerate(links, 1))
    return _render_template(prompt_template, DEFAULT_BULK_LINKS_PROMPT_TEMPLATE, {
        'candidate_profile': _profile(candidate_profile),
        'recommendation_rules': RECOMMENDATION_RULES,
        'skill_analysis_rules': SKILL_ANALYSIS_RULES,
        'custom_instructions': custom_instructions or '',
        'custom_instructions_section': _custom_instructions_section(custom_instructions),
        'schema': BULK_LINKS_SCHEMA,
        'links': links_block,
    })


def build_combined_prompt(jobs, custom_instructions='', candidate_profile=None, prompt_template=None):
    return _render_template(prompt_template, DEFAULT_COMBINED_PROMPT_TEMPLATE, {
        'candidate_profile': _profile(candidate_profile),
        'recommendation_rules': RECOMMENDATION_RULES,
        'skill_analysis_rules': SKILL_ANALYSIS_RULES,
        'custom_instructions': custom_instructions or '',
        'custom_instructions_section': _custom_instructions_section(custom_instructions),
        'schema': COMBINED_SCHEMA,
        'jobs': _combined_jobs_block(jobs),
    })


def build_enrichment_prompt(jobs, custom_instructions='', candidate_profile=None, prompt_template=None):
    return _render_template(prompt_template, DEFAULT_ENRICHMENT_PROMPT_TEMPLATE, {
        'candidate_profile': _profile(candidate_profile),
        'recommendation_rules': RECOMMENDATION_RULES,
        'skill_analysis_rules': SKILL_ANALYSIS_RULES,
        'custom_instructions': custom_instructions or '',
        'custom_instructions_section': _custom_instructions_section(custom_instructions),
        'schema': ENRICHMENT_SCHEMA,
        'jobs': _enrichment_jobs_block(jobs),
    })


def build_prompt(jobs, custom_instructions='', candidate_profile=None, prompt_template=None):
    return _render_template(prompt_template, DEFAULT_EVALUATION_PROMPT_TEMPLATE, {
        'candidate_profile': _profile(candidate_profile),
        'recommendation_rules': RECOMMENDATION_RULES,
        'skill_analysis_rules': SKILL_ANALYSIS_RULES,
        'custom_instructions': custom_instructions or '',
        'custom_instructions_section': _custom_instructions_section(custom_instructions),
        'schema': EVALUATION_SCHEMA,
        'jobs': _evaluation_jobs_block(jobs),
    })
