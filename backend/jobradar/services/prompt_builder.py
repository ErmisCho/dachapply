import json

from django.db import connection

from jobradar.models import DEFAULT_CANDIDATE_PROFILE, UserProfile
from jobradar.services.cleaning import clean_job_location

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
Return valid JSON only. No markdown.

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
Preserve job_id exactly. Put links only in url. Never put URLs in company or title. For location, use the city only when a city is known (for example Vienna, not AUT 1100 Vienna). Do not invent experience or facts; use unknown/empty values when needed.
Return valid JSON only. No markdown.

CANDIDATE PROFILE:
{candidate_profile}

{recommendation_rules}

{skill_analysis_rules}
{custom_instructions_section}
EXPECTED JSON SCHEMA:
{schema}

JOBS:
{jobs}'''

DEFAULT_ENRICHMENT_PROMPT_TEMPLATE = '''Extract missing structured job details from the provided job URLs/descriptions. Use only information visible in the text or URL context. If a detail is unknown, use an empty string or unknown. For location, use the city only when a city is known (for example Vienna, not AUT 1100 Vienna). Do not invent facts.
Use the candidate profile only as context for which job details are most relevant; do not evaluate unless the schema asks for it.
Return valid JSON only. No markdown.
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
Use only information you can infer from the provided link text and any job description text supplied by the user. Put the complete collected job text in original_source_text without summarizing or truncating it. If you cannot access a page or a detail is unknown, use an empty string or unknown. Do not invent experience or facts.
Return valid JSON only. No markdown.

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
    defaults={field: encode_profile_value(field, '') for field in PROFILE_FIELD_NAMES if field != 'candidate_profile'}
    defaults['candidate_profile']=DEFAULT_CANDIDATE_PROFILE
    profile, _ = UserProfile.objects.get_or_create(user=user, defaults=defaults)
    if not profile.candidate_profile:
        profile.candidate_profile = DEFAULT_CANDIDATE_PROFILE
        profile.save(update_fields=['candidate_profile'])
    return profile


def build_candidate_profile_text(user):
    if not getattr(user, 'is_authenticated', False):
        return DEFAULT_CANDIDATE_PROFILE
    profile = user_profile_settings(user)
    parts = []
    for label, field in PROFILE_FIELDS:
        value = (decode_profile_value(getattr(profile, field, '')) or '').strip()
        if field == 'candidate_profile' and not value:
            value = DEFAULT_CANDIDATE_PROFILE
        if value:
            parts.append(f'{label}:\n{value}')
    return '\n\n'.join(parts) or DEFAULT_CANDIDATE_PROFILE


def _profile(candidate_profile=None):
    return (candidate_profile or DEFAULT_CANDIDATE_PROFILE).strip()


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
        desc=(j.raw_description or '')[:3500]
        lines += [f'Job ID: {j.id}', f'Company: {j.company}', f'Title: {j.title}', f'Location: {clean_job_location(j.location)}', f'Work mode: {j.work_mode}', f'URL: {j.url}', f'Salary: {j.salary_info}', f'Language requirements: {j.language_requirements}', f'Description: {desc}', '---']
    return '\n'.join(lines)


def _combined_jobs_block(jobs):
    lines=[]
    for j in jobs:
        lines += [f'Job ID: {j.id}', f'Current company: {j.company}', f'Current title: {j.title}', f'URL: {j.url}', f'Location: {clean_job_location(j.location)}', f'Work mode: {j.work_mode}', f'Salary: {j.salary_info}', f'Languages: {j.language_requirements}', f'Description: {(j.raw_description or "")[:3500]}', '---']
    return '\n'.join(lines)


def _enrichment_jobs_block(jobs):
    lines=[]
    for j in jobs:
        lines += [f'Job ID: {j.id}', f'Current company: {j.company}', f'Current title: {j.title}', f'URL: {j.url}', f'Current location: {clean_job_location(j.location)}', f'Current description: {(j.raw_description or "")[:2500]}', '---']
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
