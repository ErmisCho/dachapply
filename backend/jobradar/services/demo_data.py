from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone

from jobradar.models import ApplicationNote, FollowUp, InviteCode, JobEvaluation, JobLead, UserProfile

DEMO_USERNAME = 'demo@dachapply.com'
DEMO_PASSWORD = 'DemoApply2026!'

DEMO_PROFILE = '''Senior backend/search engineer targeting DACH roles. Strongest fits: Python backend, Django/FastAPI, APIs, SQL/PostgreSQL, search/RAG, AI product engineering, data/platform-adjacent backend work, and pragmatic reliability. Comfortable with Docker, Linux, Redis/RabbitMQ, Elasticsearch/OpenSearch, LangChain/LangGraph, and cloud basics. German B2 in progress, English C2. Prefer Vienna, Berlin, Munich, Zurich, or remote/hybrid roles. Penalize frontend-heavy React roles, pure DevOps/SRE, deep Spark/Kafka ownership without support, and roles requiring fluent German C1+ as a hard gate. Be honest about cloud/Terraform/Spark depth and do not invent experience.'''


def _user(username, email=None, password=None, first_name=''):
    User = get_user_model()
    user, _ = User.objects.get_or_create(
        username=username,
        defaults={'email': email or username, 'first_name': first_name},
    )
    changed = False
    if email and user.email != email:
        user.email = email
        changed = True
    if first_name and user.first_name != first_name:
        user.first_name = first_name
        changed = True
    if password:
        user.set_password(password)
        changed = True
    if changed:
        user.save()
    return user


def _profile(user, **defaults):
    profile, _ = UserProfile.objects.get_or_create(user=user)
    changed = False
    for key, value in defaults.items():
        if getattr(profile, key) != value:
            setattr(profile, key, value)
            changed = True
    if changed:
        profile.save()
    return profile


def _upsert_job(owner, data, referral_user=None):
    url = data['url']
    qs = JobLead.objects.filter(url=url)
    existing = qs.filter(created_by=owner).first() or qs.filter(submitted_for=owner).first()
    defaults = data.copy()
    evaluation = defaults.pop('evaluation')
    notes = defaults.pop('notes', [])
    followups = defaults.pop('followups', [])
    if referral_user:
        defaults.update({'created_by': referral_user, 'submitted_for': owner, 'source': 'friend'})
    else:
        defaults.update({'created_by': owner, 'submitted_for': None, 'source': defaults.get('source') or 'demo'})
    if existing:
        job = existing
        for key, value in defaults.items():
            setattr(job, key, value)
        job.save()
    else:
        job = JobLead.objects.create(**defaults)
    job.evaluations.all().delete()
    JobEvaluation.objects.create(job=job, **evaluation)
    ApplicationNote.objects.filter(job=job).delete()
    for note in notes:
        ApplicationNote.objects.create(job=job, created_by=owner, **note)
    FollowUp.objects.filter(job=job).delete()
    for followup in followups:
        FollowUp.objects.create(job=job, **followup)
    return job


def ensure_demo_user():
    """Create/refresh the public demo account with rich showcase data."""
    today = timezone.localdate()
    demo = _user(DEMO_USERNAME, DEMO_USERNAME, DEMO_PASSWORD, 'Demo')
    _profile(
        demo,
        candidate_profile=DEMO_PROFILE,
        target_roles='Python Backend, Search/RAG Engineer, AI Engineer, Data/Platform Backend',
        preferred_locations='Vienna, Berlin, Munich, Zurich, remote/hybrid DACH',
        language_levels='English C2, German B2 in progress',
        preferred_stack='Python, Django, FastAPI, PostgreSQL, Elasticsearch/OpenSearch, RAG, Docker, Redis',
        red_flags='Frontend-heavy roles, pure DevOps/SRE, hard C1 German, deep Spark/Kafka/Terraform ownership without ramp-up',
        selling_points='Backend delivery, search/RAG systems, pragmatic product engineering, clear gap awareness',
    )

    anna = _user('anna.referrer@example.com', 'anna.referrer@example.com', first_name='Anna')
    max_ = _user('max.referrer@example.com', 'max.referrer@example.com', first_name='Max')
    sophie = _user('sophie.recruiter@example.com', 'sophie.recruiter@example.com', first_name='Sophie')
    pending = _user('lara.pending@example.com', 'lara.pending@example.com', first_name='Lara')
    _profile(anna, submit_for=demo, requested_submit_for=None)
    _profile(max_, submit_for=demo, requested_submit_for=None)
    _profile(sophie, submit_for=demo, requested_submit_for=None)
    _profile(pending, submit_for=None, requested_submit_for=demo)

    InviteCode.objects.update_or_create(code='FRIEND-DEMO', defaults={'label': 'Demo friends invite', 'active': True})

    # Reset the demo dashboard on every seed/login so imported, edited, or stale
    # demo jobs never accumulate. This removes jobs owned by the demo user plus
    # friend-submitted jobs visible in the demo user's dashboard; evaluations,
    # notes, and follow-ups are deleted by cascade.
    JobLead.objects.filter(Q(created_by=demo) | Q(submitted_for=demo)).delete()

    common_eval = {
        'nice_to_have_skills': ['Docker', 'Azure', 'Redis'],
        'structured_json_raw': {'source': 'seed_demo'},
    }
    jobs = [
        {
            'company': 'Dynatrace', 'title': 'Senior Python Backend Engineer', 'location': 'Vienna', 'work_mode': 'hybrid',
            'url': 'https://demo.dachapply.local/jobs/dynatrace-python-backend', 'status': 'interview', 'status_date': today - timedelta(days=10),
            'interview_stage': 3, 'interview_total': 5, 'feedback_due_date': today + timedelta(days=2), 'last_update_date': today - timedelta(days=1),
            'raw_description': 'Backend platform role using Python services, APIs, PostgreSQL, observability, async workers, and pragmatic cloud delivery.',
            'language_requirements': 'English required; German helpful', 'salary_info': '€75k-90k',
            'evaluation': {**common_eval, 'fit_score': 91, 'priority': 'high', 'recommendation': 'apply', 'summary': 'Excellent Python backend and Vienna hybrid fit with credible search/platform overlap.', 'main_match_reasons': ['Python backend/API ownership', 'Vienna hybrid preference match', 'SQL and platform reliability overlap'], 'main_gaps': ['Clarify depth of cloud production ownership'], 'required_skills': ['Python', 'PostgreSQL', 'REST APIs', 'Docker'], 'matched_skills': ['Python', 'PostgreSQL', 'REST APIs', 'Docker'], 'missing_skills': ['Terraform'], 'cv_adjustment_notes': 'Lead with backend ownership and measurable service reliability.', 'interview_prep_notes': 'Prepare API design, debugging, and observability stories.', 'risk_notes': 'Cloud depth may be probed.', 'next_action': 'Prepare stage 3 system-design interview.'},
            'notes': [{'note_type': 'interview_prep', 'note': 'Stage 3: prepare observability and API scaling examples.'}],
            'followups': [{'follow_up_date': today + timedelta(days=2), 'reason': 'Check recruiter feedback after stage 3'}],
        },
        {
            'company': 'AI Search Lab', 'title': 'RAG / Search Engineer', 'location': 'Vienna', 'work_mode': 'hybrid',
            'url': 'https://demo.dachapply.local/jobs/ai-search-rag', 'status': 'interview', 'status_date': today - timedelta(days=18),
            'interview_stage': 2, 'interview_total': 4, 'feedback_due_date': today - timedelta(days=1), 'last_update_date': today - timedelta(days=6),
            'raw_description': 'Search and RAG role using embeddings, LangChain, retrieval evaluation, Python APIs, and OpenSearch.',
            'language_requirements': 'English; German B1+', 'salary_info': '€70k-85k',
            'evaluation': {**common_eval, 'fit_score': 89, 'priority': 'high', 'recommendation': 'apply', 'summary': 'Very strong RAG/search alignment; interview follow-up is overdue.', 'main_match_reasons': ['RAG and semantic search are core strengths', 'Python API work matches', 'OpenSearch/Elasticsearch overlap'], 'main_gaps': ['Need to show production retrieval evaluation depth'], 'required_skills': ['Python', 'RAG', 'LangChain', 'OpenSearch'], 'matched_skills': ['Python', 'RAG', 'LangChain', 'OpenSearch'], 'missing_skills': ['Kubernetes'], 'cv_adjustment_notes': 'Add concrete RAG evaluation and search relevance metrics.', 'interview_prep_notes': 'Prepare retrieval-quality and hallucination-mitigation examples.', 'risk_notes': 'May expect deeper ML evaluation vocabulary.', 'next_action': 'Send follow-up today; overdue by one day.'},
            'notes': [{'note_type': 'follow_up', 'note': 'Feedback promised this week; follow up politely.'}],
            'followups': [{'follow_up_date': today - timedelta(days=1), 'reason': 'Overdue feedback from RAG interview'}],
        },
        {
            'company': 'FinTech GmbH', 'title': 'Django Developer', 'location': 'Berlin', 'work_mode': 'remote',
            'url': 'https://demo.dachapply.local/jobs/fintech-django', 'status': 'applied', 'status_date': today - timedelta(days=7),
            'interview_stage': None, 'interview_total': None, 'feedback_due_date': today + timedelta(days=14), 'last_update_date': today - timedelta(days=7),
            'raw_description': 'Django and PostgreSQL product role for payments workflows, REST APIs, Celery workers, and compliance-heavy feature delivery.',
            'language_requirements': 'English; German nice to have', 'salary_info': '€68k-82k',
            'evaluation': {**common_eval, 'fit_score': 84, 'priority': 'high', 'recommendation': 'apply', 'summary': 'Strong Django/backend match with finance-domain credibility.', 'main_match_reasons': ['Django and PostgreSQL are direct matches', 'Finance/enterprise background helps', 'Remote Berlin works well'], 'main_gaps': ['Payments compliance domain may need ramp-up'], 'required_skills': ['Python', 'Django', 'PostgreSQL', 'Celery'], 'matched_skills': ['Python', 'Django', 'PostgreSQL'], 'missing_skills': ['Payments compliance'], 'cv_adjustment_notes': 'Emphasize finance/enterprise experience and reliable delivery.', 'interview_prep_notes': 'Prepare transaction consistency and background job examples.', 'risk_notes': 'Domain specifics may be new.', 'next_action': 'Wait one week, then follow up.'},
            'followups': [{'follow_up_date': today + timedelta(days=7), 'reason': 'Follow up on application'}],
        },
        {
            'company': 'CloudOps AG', 'title': 'Platform Reliability Engineer', 'location': 'Munich', 'work_mode': 'hybrid',
            'url': 'https://demo.dachapply.local/jobs/cloudops-platform', 'status': 'reviewed', 'status_date': None,
            'interview_stage': None, 'interview_total': None, 'feedback_due_date': None, 'last_update_date': today - timedelta(days=2),
            'raw_description': 'Platform reliability role with Kubernetes, Terraform, CI/CD, Linux, observability, Python automation, and on-call.',
            'language_requirements': 'English; German B2', 'salary_info': '€78k-95k',
            'evaluation': {**common_eval, 'fit_score': 63, 'priority': 'medium', 'recommendation': 'maybe', 'summary': 'Some Python/Linux overlap, but pure platform depth and on-call may be a stretch.', 'main_match_reasons': ['Python automation and Linux overlap', 'Reliability mindset is relevant'], 'main_gaps': ['Deep Kubernetes/Terraform/on-call expectations', 'Munich hybrid may require relocation/travel'], 'required_skills': ['Kubernetes', 'Terraform', 'Linux', 'CI/CD'], 'matched_skills': ['Python', 'Linux'], 'missing_skills': ['Kubernetes', 'Terraform', 'CI/CD'], 'cv_adjustment_notes': 'Only apply if positioning as backend-platform bridge.', 'interview_prep_notes': 'Prepare honest Kubernetes and incident examples.', 'risk_notes': 'Pure SRE expectations may cap fit.', 'next_action': 'Keep as maybe; lower priority than backend/search roles.'},
        },
        {
            'company': 'Helvetic Frontend Studio', 'title': 'React Frontend Developer', 'location': 'Zurich', 'work_mode': 'onsite',
            'url': 'https://demo.dachapply.local/jobs/helvetic-react', 'status': 'skipped', 'status_date': None,
            'interview_stage': None, 'interview_total': None, 'feedback_due_date': None, 'last_update_date': today - timedelta(days=4),
            'raw_description': 'Frontend-heavy React/TypeScript role with design systems and onsite Zurich collaboration.',
            'language_requirements': 'English; German helpful', 'salary_info': 'CHF 105k-120k',
            'evaluation': {**common_eval, 'fit_score': 39, 'priority': 'low', 'recommendation': 'skip', 'summary': 'Low alignment: frontend-heavy, onsite, and not a core target role.', 'main_match_reasons': ['General software engineering experience transfers'], 'main_gaps': ['React/TypeScript is not a strongest fit', 'Onsite Zurich constraint', 'Design systems focus'], 'required_skills': ['React', 'TypeScript', 'CSS'], 'matched_skills': ['JavaScript'], 'missing_skills': ['React', 'TypeScript', 'Design systems'], 'cv_adjustment_notes': 'Do not spend CV tailoring time unless strategy changes.', 'interview_prep_notes': 'N/A unless pursuing frontend pivot.', 'risk_notes': 'Would dilute backend/search positioning.', 'next_action': 'Skip.'},
        },
        {
            'company': 'Green Energy Analytics', 'title': 'Backend Data Engineer', 'location': 'Berlin', 'work_mode': 'remote',
            'url': 'https://demo.dachapply.local/referrals/green-energy-analytics', 'status': 'to_apply', 'status_date': None,
            'interview_stage': None, 'interview_total': None, 'feedback_due_date': None, 'last_update_date': today,
            'submitted_by': 'Anna', 'submitter_reason': 'Anna knows the hiring manager and thinks the Python/API plus analytics mix is a fit.',
            'raw_description': 'Referral from Anna: Python data APIs, SQL models, Airflow-light orchestration, product analytics, and stakeholder collaboration.',
            'language_requirements': 'English required', 'salary_info': '€72k-88k',
            'evaluation': {**common_eval, 'fit_score': 78, 'priority': 'medium', 'recommendation': 'apply', 'summary': 'Good referral with Python/SQL overlap; data orchestration depth should be framed carefully.', 'main_match_reasons': ['Warm referral from Anna', 'Python/SQL/API overlap', 'Remote Berlin fits'], 'main_gaps': ['Airflow/data platform depth is not the strongest evidence'], 'required_skills': ['Python', 'SQL', 'APIs', 'Airflow'], 'matched_skills': ['Python', 'SQL', 'APIs'], 'missing_skills': ['Airflow'], 'cv_adjustment_notes': 'Tailor with analytics/data-adjacent backend examples.', 'interview_prep_notes': 'Prepare pipeline reliability and product analytics stories.', 'risk_notes': 'May become data-platform heavy.', 'next_action': 'Ask Anna for intro details, then apply.'},
        },
        {
            'company': 'MedTech Rails GmbH', 'title': 'Python API Engineer', 'location': 'Munich', 'work_mode': 'hybrid',
            'url': 'https://demo.dachapply.local/referrals/medtech-python-api', 'status': 'interview', 'status_date': today - timedelta(days=3),
            'interview_stage': 1, 'interview_total': 3, 'feedback_due_date': today + timedelta(days=5), 'last_update_date': today - timedelta(days=1),
            'submitted_by': 'Max', 'submitter_reason': 'Max referred this after seeing the backend/API focus and realistic German requirement.',
            'raw_description': 'Referral from Max: Python/FastAPI services for healthcare workflow integrations, PostgreSQL, audit trails, and secure APIs.',
            'language_requirements': 'English, German B1/B2 helpful', 'salary_info': '€70k-86k',
            'evaluation': {**common_eval, 'fit_score': 82, 'priority': 'high', 'recommendation': 'apply', 'summary': 'Strong referred API/backend role; currently in first interview round.', 'main_match_reasons': ['Warm referral from Max', 'Python/FastAPI/PostgreSQL match', 'German requirement realistic'], 'main_gaps': ['Healthcare compliance domain is new'], 'required_skills': ['Python', 'FastAPI', 'PostgreSQL', 'REST APIs'], 'matched_skills': ['Python', 'FastAPI', 'PostgreSQL', 'REST APIs'], 'missing_skills': ['Healthcare compliance'], 'cv_adjustment_notes': 'Emphasize secure API design and auditability.', 'interview_prep_notes': 'Prepare examples around integrations and data privacy tradeoffs.', 'risk_notes': 'Compliance vocabulary may be probed.', 'next_action': 'Prepare for stage 1 technical screen.'},
            'notes': [{'note_type': 'interview_prep', 'note': 'Mention privacy-by-design and API audit trail examples.'}],
        },
        {
            'company': 'Swiss AI Systems', 'title': 'Applied AI Backend Engineer', 'location': 'Zurich', 'work_mode': 'hybrid',
            'url': 'https://demo.dachapply.local/referrals/swiss-ai-backend', 'status': 'interview', 'status_date': today - timedelta(days=12),
            'interview_stage': 4, 'interview_total': 5, 'feedback_due_date': today + timedelta(days=1), 'last_update_date': today,
            'submitted_by': 'Sophie', 'submitter_reason': 'Sophie is a recruiter referral and flagged the role as backend-heavy, not research-heavy.',
            'raw_description': 'Recruiter referral from Sophie: applied AI backend role with Python APIs, vector search, retrieval, evaluation, and product integration.',
            'language_requirements': 'English; German optional', 'salary_info': 'CHF 125k-145k',
            'evaluation': {**common_eval, 'fit_score': 87, 'priority': 'high', 'recommendation': 'apply', 'summary': 'Strong AI/backend referral and late-stage interview; compensation and location need calibration.', 'main_match_reasons': ['Applied AI/backend rather than research-only', 'Vector search/RAG strengths match', 'Recruiter referral and late-stage process'], 'main_gaps': ['Zurich hybrid logistics and salary expectations need clarity'], 'required_skills': ['Python', 'Vector search', 'RAG', 'APIs'], 'matched_skills': ['Python', 'Vector search', 'RAG', 'APIs'], 'missing_skills': ['MLOps'], 'cv_adjustment_notes': 'Bring RAG/search product impact to the top.', 'interview_prep_notes': 'Prepare final-round tradeoffs: evaluation, latency, privacy, and rollout.', 'risk_notes': 'May test production MLOps depth.', 'next_action': 'Prepare final interview and compensation questions.'},
            'followups': [{'follow_up_date': today + timedelta(days=1), 'reason': 'Final-round feedback due'}],
        },
        {
            'company': 'Legacy Enterprise SE', 'title': 'Java Support Engineer', 'location': 'Frankfurt', 'work_mode': 'onsite',
            'url': 'https://demo.dachapply.local/jobs/legacy-java-support', 'status': 'archived', 'status_date': None,
            'interview_stage': None, 'interview_total': None, 'feedback_due_date': None, 'last_update_date': today - timedelta(days=20),
            'raw_description': 'Older archived lead: Java support, ticket triage, onsite work, and legacy enterprise maintenance.',
            'language_requirements': 'German C1 required', 'salary_info': '€60k-70k',
            'evaluation': {**common_eval, 'fit_score': 45, 'priority': 'low', 'recommendation': 'skip', 'summary': 'Archived because German C1 and support-heavy work are weak alignment.', 'main_match_reasons': ['Some Java/enterprise background'], 'main_gaps': ['German C1 hard gate', 'Support-heavy role', 'Onsite Frankfurt'], 'required_skills': ['Java', 'German C1', 'Support'], 'matched_skills': ['Java'], 'missing_skills': ['German C1', 'Support ownership'], 'cv_adjustment_notes': 'No action.', 'interview_prep_notes': 'No action.', 'risk_notes': 'Hard language gate.', 'next_action': 'Keep archived.'},
        },
    ]

    referral_map = {
        'https://demo.dachapply.local/referrals/green-energy-analytics': anna,
        'https://demo.dachapply.local/referrals/medtech-python-api': max_,
        'https://demo.dachapply.local/referrals/swiss-ai-backend': sophie,
    }
    created = [_upsert_job(demo, job, referral_map.get(job['url'])) for job in jobs]
    return demo, created
