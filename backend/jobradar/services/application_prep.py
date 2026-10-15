"""TASK-280.2: prepare a job's application documents in the background when it moves into To apply.

What to prepare comes from the stored TASK-280.1 analysis (plan_variants); how each document is made
is the existing CV/letter generator (cv_tasks.start_cv_task), one task per variant, so every variant
has the usual progress, download and readjust paths and fails on its own.

State lives in the job's workspace sidecar under 'preparation' -- the same local-only file that
already tracks the job's generated files -- so it survives a restart without a migration:
{"reason": "why nothing was started, else ''", "model": {...},
 "variants": {"cv-de": {"document": "cv"|"letter"|"message", "language": "en"|"de", "letter_template": "",
                        "status": "queued"|"running"|"ready"|"failed", "task_id": "", "error": "", "files": {...}}}}
"""
import logging
from pathlib import Path
from threading import Lock

from django.conf import settings
from django.contrib.auth import get_user_model

from jobradar.models import JobLead
from jobradar.services import cv_tasks
from jobradar.services.cv_generator import _edit_sidecar, _read_artifact_metadata, available_model_options, is_cv_owner, latest_generated_sources, load_candidate_evidence, user_templates, validate_model_capability
from jobradar.services.draft_chat import default_draft_choice
from jobradar.services.prompt_builder import build_candidate_profile_text, user_profile_settings

logger = logging.getLogger(__name__)

# AC4: the owner-visible default for a letter the posting does not mention (or calls optional).
LETTER_RULE = 'Letters the posting does not mention, or calls optional, are not prepared automatically. Generate one from the CV section if you want it.'
LANGUAGE_NAMES = {'en': 'English', 'de': 'German'}
WANT = ('required', 'preferred')
FULL_LETTER_TYPES = ('cover_letter', 'motivation_letter')
INTERRUPTED = 'Stopped before it finished (the server restarted). Retry to prepare it again.'

_lock = Lock()  # ponytail: one process serves generation (threaded runserver); a DB claim if that changes


def _kind_status(documents, types):
    """want / never / unclear / default for one kind of letter, from the analysed documents."""
    statuses = {doc.get('status') for doc in documents if doc.get('type') in types}
    if statuses & set(WANT):
        return 'want'
    if 'not_accepted' in statuses:
        return 'never'
    return 'unclear' if 'unclear' in statuses else 'default'


def plan_variants(requirements):
    """(variants, reason) for an analysed requirements dict -- the AC2/AC3 matrix, nothing else.

    Language: the explicit application language, else a clear posting language, else EN and DE.
    Letters: required/preferred ones only; not_accepted never; with nothing wanted, an unclear letter
    or message requirement gives both a full letter and a short message (minus any not accepted);
    not mentioned / optional / absent follow LETTER_RULE (none).
    """
    if not requirements:
        return [], 'Application requirements are not analysed yet. Analyse the job, then move it to To apply again or press Prepare.'
    posting = requirements.get('posting_language')
    language = requirements.get('application_language') or (posting if posting in LANGUAGE_NAMES else '')
    languages = [language] if language else ['en', 'de']
    documents = requirements.get('documents') or []
    kinds = {'letter': _kind_status(documents, FULL_LETTER_TYPES), 'message': _kind_status(documents, ('short_message',))}
    if 'want' in kinds.values():
        letters = [kind for kind, status in kinds.items() if status == 'want']
    elif 'unclear' in kinds.values():
        letters = [kind for kind, status in kinds.items() if status != 'never']
    else:
        letters = []
    motivation = _kind_status(documents, ('motivation_letter',)) == 'want' and _kind_status(documents, ('cover_letter',)) != 'want'
    letter_type = 'motivation_letter' if motivation else 'cover_letter'
    return [{'key': f'{document}-{lang}', 'document': document, 'language': lang, 'letter_type': letter_type}
            for document in ['cv', *letters] for lang in languages], ''


def _letter_template(letters, letter_type):
    # Letter keys are the owner's own (anschreiben, motivation_letter, ...); the requested type picks
    # a matching one when there is one, else the language's first.
    hints = ('motivation',) if letter_type == 'motivation_letter' else ('anschreiben', 'cover')
    return next((key for key in letters if any(hint in key.lower() for hint in hints)), next(iter(letters), ''))


def _state(job, user):
    return _read_artifact_metadata(job, user).get('preparation') or {}


def _save(job, user_id, change):
    def edit(data):
        change(data.setdefault('preparation', {}))
    return _edit_sidecar(job, user_id, edit)


def _gate(job, user):
    """(reason, variants, context, choice). A non-empty reason means nothing may start (AC1)."""
    if job.pending_source_text:
        return 'Choose which job text to use (Keep current or Use fetched) before documents are prepared.', [], '', None
    if not job.is_meaningful_source(job.source_text):
        return 'The job has no usable posting text yet.', [], '', None
    variants, reason = plan_variants(job.application_requirements)
    if reason:
        return reason, [], '', None
    templates = user_templates(user)
    for variant in variants:
        language = LANGUAGE_NAMES[variant['language']]
        if variant['language'] not in templates:
            return f'No {language} CV template is stored on this account.', [], '', None
        if variant['document'] != 'cv':
            letters = templates[variant['language']]['letters']
            if not letters:
                return f'No {language} letter template is stored on this account.', [], '', None
            variant['letter_template'] = _letter_template(letters, variant['letter_type'])
    option, effort, _ = default_draft_choice(available_model_options())
    if not option:
        return 'No document model is available on this machine.', [], '', None
    choice = {'provider': option['provider'], 'model': option['key'], 'effort': effort, 'speed': 'normal'}
    try:
        validate_model_capability(*choice.values(), needs_tools=True)
        profile = user_profile_settings(user)
        context = load_candidate_evidence(build_candidate_profile_text(user), profile.learned_application_preferences, profile.candidate_evidence)
    except (RuntimeError, ValueError) as exc:
        return str(exc), [], '', None
    return '', variants, context, choice


def _start(job, user, variants, context, choice, suffix):
    """Start one background task per variant. Caller holds _lock and has saved them as queued."""
    for variant in variants:
        key, document = variant['key'], variant['document']
        options = {'short_message': True} if document == 'message' else {}
        if suffix:
            options['name_suffix'] = variant['language'].upper()

        def finished(task_id, key=key):
            _finish(job.id, user.pk, key, task_id)
        try:
            task_id = cv_tasks.start_cv_task(
                job.id, user.pk, context, variant['language'], variant.get('letter_template', ''), document != 'cv',
                choice['provider'], choice['model'], choice['effort'], choice['speed'], create_cv=document == 'cv',
                auto_clipboard=False, generation_options=options, mark_ready=False, on_finish=finished)
        except Exception as exc:  # one variant that cannot start must not stop the others (AC5)
            _save(job, user.pk, lambda prep, key=key, error=str(exc)[:500]: prep['variants'][key].update(status='failed', error=error))
            continue

        def running(prep, key=key, task_id=task_id):
            # A fast task can finish before this runs; its recorded outcome wins.
            if prep['variants'][key]['status'] == 'queued':
                prep['variants'][key].update(status='running', task_id=task_id)
        _save(job, user.pk, running)


def _finish(job_id, user_id, key, task_id):
    job = JobLead.objects.filter(pk=job_id).first()
    task = cv_tasks.get_cv_task(task_id, user_id) or {}
    if not job:
        return
    artifacts = task.get('artifacts') or {}
    files = {name: artifacts[name] for name in ('cv_tex', 'cv_pdf', 'letter_tex', 'letter_pdf') if artifacts.get(name)}
    ready = task.get('status') == 'ready'

    def record(prep):
        variant = prep.get('variants', {}).get(key)
        if variant is None or variant.get('task_id') not in ('', None, task_id):
            return  # a newer retry owns this variant
        variant.update(task_id=task_id, status='ready' if ready else 'failed', files=files if ready else {},
                       error='' if ready else task.get('error') or 'Stopped before it finished.')
    _save(job, user_id, record)


def prepare(job_id, user, retry=False):
    """Start preparation for a To-apply job, or with retry, re-run only its failed variants.

    Returns the public state, or None when this account/server cannot generate at all. Concurrency
    safe: a second call (a double transition) finds the variants already recorded and starts nothing.
    """
    if not is_cv_owner(user) or not settings.CODEX_CV_WORKSPACE or not Path(settings.CODEX_CV_WORKSPACE).is_dir():
        return None
    job = JobLead.objects.filter(pk=job_id).first()
    if not job:
        return None
    with _lock:
        state = public_state(job, user)
        # AC1: only To apply (and, for a retry, the Ready to submit it may have moved to). New/Reviewed
        # and Applied or later are never generated for.
        allowed = ('to_apply', 'ready_to_submit') if retry else ('to_apply',)
        if job.status not in allowed:
            return state
        failed = [variant for variant in state['variants'] if variant['status'] == 'failed']
        if state['variants'] and not (retry and failed):
            return state
        reason, variants, context, choice = _gate(job, user)
        if not reason and not state['variants'] and any(latest_generated_sources(job, user)):
            # AC5: files the owner already generated are theirs; automatic drafts never join or replace them.
            reason ='Generated files already exist for this job, so nothing was prepared automatically. Generate more from the CV section.'
        if reason:
            if not state['variants']:
                _save(job, user.pk, lambda prep: prep.update(reason=reason, variants={}))
            return public_state(job, user, reason_override=reason if state['variants'] else None)
        if state['variants']:
            # AC5: retry targets only failed variants; ready and running ones are left alone.
            wanted = {variant['key'] for variant in failed}
            stored = _state(job, user)['variants']
            variants = [{**stored[key], 'key': key, 'letter_type': ''} for key in wanted]
            suffix = len({variant['language'] for variant in stored.values()}) > 1
        else:
            suffix = len({variant['language'] for variant in variants}) > 1

        def queue(prep):
            prep.update(reason='', model=choice)
            prep.setdefault('variants', {})
            for variant in variants:
                prep['variants'][variant['key']] = {'document': variant['document'], 'language': variant['language'],
                                                    'letter_template': variant.get('letter_template', ''),
                                                    'status': 'queued', 'task_id': '', 'error': '', 'files': {}}
        _save(job, user.pk, queue)
        _start(job, user, variants, context, choice, suffix)
    return public_state(job, user)


def prepare_on_to_apply(job_id, user_id):
    """The status-transition hook: never raises, so a generation problem cannot fail the status save."""
    try:
        user = get_user_model().objects.filter(pk=user_id).first()
        if user:
            prepare(job_id, user)
    except Exception:
        logger.exception('Preparing application documents for job %s failed', job_id)


def public_state(job, user, reason_override=None):
    """What the job page shows: each variant with live progress, and interrupted runs as failed."""
    state = _state(job, user)
    variants = []
    for key, stored in (state.get('variants') or {}).items():
        variant = {'key': key, **stored}
        if variant['status'] in ('queued', 'running'):
            live = cv_tasks.get_cv_task(variant['task_id'], user.pk) if variant['task_id'] else None
            if live:
                variant.update(progress=live['progress'], step_label=live['step_label'], estimated_seconds_remaining=live['estimated_seconds_remaining'])
            elif variant['task_id']:
                variant.update(status='failed', error=INTERRUPTED)
        if variant['status'] == 'ready':
            variant['missing'] = not any(Path(path).is_file() for path in variant.get('files', {}).values())
        variants.append(variant)
    order = {'cv': 0, 'letter': 1, 'message': 2}
    variants.sort(key=lambda variant: (order.get(variant['document'], 3), variant['language']))
    return {'reason': reason_override if reason_override is not None else state.get('reason', ''), 'rule': LETTER_RULE,
            'model': state.get('model') or {}, 'variants': variants}
