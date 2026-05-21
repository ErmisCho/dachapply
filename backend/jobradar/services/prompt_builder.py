CANDIDATE_PROFILE = '''Software Engineer based in Vienna. Strong Python backend experience. Django, FastAPI, REST APIs, Java. RAG, semantic search, LangChain, LangGraph. Elasticsearch/OpenSearch. SQL, PostgreSQL, MySQL. Docker, Linux, Kubernetes basics, AWS basics, Azure learning in progress. RabbitMQ, Redis, async/background processing from personal projects. Enterprise background in finance, telecom, and AI/search systems. German: professional working proficiency, B2 completed, C1 in progress. English: C2 certified. Stronger fit for Python Backend, AI Engineer, RAG, Search, Data Engineering, Platform, and reliability-focused roles. Weaker fit for frontend-heavy React/TypeScript roles, pure DevOps/SRE roles, pure ML research roles, and roles requiring deep professional cloud/Spark/Terraform experience. Do not invent experience. Be honest about gaps and hiring risk.'''

def build_bulk_links_prompt(links, custom_instructions=''):
    lines=[
        'You will receive a list of job links. For each link, extract job details and evaluate the job against the candidate profile below.',
        'Important: put the link only in the url field. Never put a URL in company or title. Company must be the employer name, or Unknown company if unknown. Title must be the position name, or Untitled role if unknown.',
        'Use only information you can infer from the provided link text and any job description text supplied by the user. If you cannot access a page or a detail is unknown, use an empty string or unknown. Do not invent experience or facts.',
        'Return valid JSON only. No markdown.',
        '',
        'CANDIDATE PROFILE:',
        CANDIDATE_PROFILE,
        '',
        'EXPECTED JSON SCHEMA:',
        '{"jobs":[{"temp_id":"link_1","url":"https://...","company":"...","title":"...","location":"...","source":"...","raw_description":"...","salary_info":"...","language_requirements":"...","work_mode":"onsite|hybrid|remote|unknown","evaluation":{"fit_score":0,"priority":"high|medium|low","recommendation":"apply|maybe|skip","summary":"...","main_match_reasons":["..."],"main_gaps":["..."],"required_skills":["..."],"nice_to_have_skills":["..."],"matched_skills":["..."],"missing_skills":["..."],"cv_adjustment_notes":"...","interview_prep_notes":"...","risk_notes":"...","next_action":"..."}}],"strategic_advice":"..."}',
        ''
    ]
    if custom_instructions: lines += ['CUSTOM INSTRUCTIONS:', custom_instructions, '']
    lines += ['JOB LINKS:']
    for i, link in enumerate(links, 1):
        lines.append(f'link_{i}: {link}')
    return '\n'.join(lines)


def build_combined_prompt(jobs, custom_instructions=''):
    lines=[
        'For each existing job below, first fill missing/incorrect job details, then evaluate the job against the candidate profile.',
        'Preserve job_id exactly. Put links only in url. Never put URLs in company or title. Do not invent experience or facts; use unknown/empty values when needed.',
        'Return valid JSON only. No markdown.',
        '', 'CANDIDATE PROFILE:', CANDIDATE_PROFILE, '',
        'EXPECTED JSON SCHEMA:',
        '{"jobs":[{"job_id":1,"url":"https://...","company":"...","title":"...","location":"...","source":"...","raw_description":"...","salary_info":"...","language_requirements":"...","work_mode":"onsite|hybrid|remote|unknown","evaluation":{"fit_score":0,"priority":"high|medium|low","recommendation":"apply|maybe|skip","summary":"...","main_match_reasons":["..."],"main_gaps":["..."],"required_skills":["..."],"nice_to_have_skills":["..."],"matched_skills":["..."],"missing_skills":["..."],"cv_adjustment_notes":"...","interview_prep_notes":"...","risk_notes":"...","next_action":"..."}}],"strategic_advice":"..."}',
        ''
    ]
    if custom_instructions: lines += ['CUSTOM INSTRUCTIONS:', custom_instructions, '']
    lines += ['JOBS:']
    for j in jobs:
        lines += [f'Job ID: {j.id}', f'Current company: {j.company}', f'Current title: {j.title}', f'URL: {j.url}', f'Location: {j.location}', f'Work mode: {j.work_mode}', f'Salary: {j.salary_info}', f'Languages: {j.language_requirements}', f'Description: {(j.raw_description or "")[:3500]}', '---']
    return '\n'.join(lines)


def build_enrichment_prompt(jobs, custom_instructions=''):
    lines=[
        'Extract missing structured job details from the provided job URLs/descriptions. Use only information visible in the text or URL context. If a detail is unknown, use an empty string or unknown. Do not invent facts.',
        'Return valid JSON only. No markdown.',
        'For each job, preserve job_id exactly so the app can update the right record.',
        '',
        'EXPECTED JSON SCHEMA:',
        '{"job_updates":[{"job_id":1,"company":"...","title":"...","location":"...","url":"...","source":"...","raw_description":"...","salary_info":"...","language_requirements":"...","work_mode":"onsite|hybrid|remote|unknown","notes":"any uncertainty or assumptions"}]}',
        ''
    ]
    if custom_instructions: lines += ['CUSTOM INSTRUCTIONS:', custom_instructions, '']
    lines += ['JOBS NEEDING DETAILS:']
    for j in jobs:
        lines += [f'Job ID: {j.id}', f'Current company: {j.company}', f'Current title: {j.title}', f'URL: {j.url}', f'Current location: {j.location}', f'Current description: {(j.raw_description or "")[:2500]}', '---']
    return '\n'.join(lines)

def build_prompt(jobs, custom_instructions=''):
    lines=[
        'Evaluate these DACH software engineering jobs against the candidate profile.',
        'Be honest, direct, and do not invent experience. Consider DACH market fit, German/English requirements, Python, Django, FastAPI, backend, AI/RAG, search, data, Docker, Linux, SQL, Redis, RabbitMQ, Elasticsearch/OpenSearch, Azure basics, and reliability engineering.',
        'Return valid JSON only. No markdown.',
        '', 'CANDIDATE PROFILE:', CANDIDATE_PROFILE, ''
    ]
    if custom_instructions: lines += ['CUSTOM INSTRUCTIONS:', custom_instructions, '']
    lines += ['EXPECTED JSON SCHEMA:', '{"evaluations":[{"job_id":1,"company":"...","title":"...","fit_score":0,"priority":"high|medium|low","recommendation":"apply|maybe|skip","summary":"...","main_match_reasons":["..."],"main_gaps":["..."],"required_skills":["..."],"nice_to_have_skills":["..."],"matched_skills":["..."],"missing_skills":["..."],"cv_adjustment_notes":"...","interview_prep_notes":"...","risk_notes":"...","next_action":"..."}],"overall_ranking":[{"job_id":1,"rank":1,"reason":"..."}],"strategic_advice":"..."}', '', 'JOBS:']
    for j in jobs:
        desc=(j.raw_description or '')[:3500]
        lines += [f'Job ID: {j.id}', f'Company: {j.company}', f'Title: {j.title}', f'Location: {j.location}', f'Work mode: {j.work_mode}', f'URL: {j.url}', f'Salary: {j.salary_info}', f'Language requirements: {j.language_requirements}', f'Description: {desc}', '---']
    return '\n'.join(lines)
