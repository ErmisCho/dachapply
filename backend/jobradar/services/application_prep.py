"""TASK-280.2: prepare a job's application documents in the background when it moves into To apply.

What to prepare comes from the stored TASK-280.1 analysis (plan_variants); how each document is made
is the existing CV/letter generator (cv_tasks.start_cv_task), one task per variant, so every variant
has the usual progress, download and readjust paths and fails on its own.

State lives in the job's workspace sidecar under 'preparation' -- the same local-only file that
already tracks the job's generated files -- so it survives a restart without a migration:
{"reason": "why nothing was started, else ''", "model": {...},
 "variants": {"cv-de": {"document": "cv"|"letter"|"message", "language": "en"|"de", "letter_template": "",
                        "status": "queued"|"running"|"ready"|"failed", "task_id": "", "error": "", "files": {...}}}}

TASK-280.3 adds the owner's review beside it, in the same sidecar: per variant "review" ("keep" |
"discard"; absent = an unreviewed draft) and "adjust_task_id"/"adjust_error"; per preparation
"selection" {"keys": [...], "files": [...]} (the final package) and "invalidated" (why a selection
was cleared). Ready to submit follows the selection, never generation.

TASK-312: preparation also starts when an apply/maybe evaluation is imported for a New, Reviewed or
To apply job (json_importer.create_evaluation), and variants no longer all start at once: they wait in
one FIFO queue across all jobs (_queue, in memory) and at most settings.PREP_QUEUE_CONCURRENCY run.
Each variant also records "queued_at"/"started_at"/"finished_at" (ISO) and may be "cancelled"; the
sidecar stays the durable copy, so resume_queue rebuilds the queue from it after a restart.

TASK-317: a variant -- or a requirements analysis (the preparation itself) -- that failed on the
provider's usage limit records "retry_at" (ISO: the reset plus a minute, or half an hour on) and
"auto_retries"; one Timer (_timer) wakes retry_due, which re-queues it through queue_action's retry,
at most AUTO_RETRIES times. Any other failure clears retry_at and is never retried automatically.
"""
import heapq
import io
import logging
import re
import tempfile
import time
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from threading import Lock, RLock, Thread, Timer

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import close_old_connections
from django.db.models import Q
from django.utils import timezone

from jobradar.models import JobEvaluation, JobLead, UserProfile
from jobradar.services import cv_tasks, job_evaluator
from jobradar.services.access import accessible_jobs
from jobradar.services.application_requirements import DOCUMENT_STATUSES, DOCUMENT_TYPES, POSTING_LANGUAGES, normalize_application_requirements
from jobradar.services.cv_generator import _edit_sidecar, _package_filename, _read_artifact_metadata, applicant_name, available_model_options, cv_default_choice, is_cv_owner, latest_generated_sources, load_candidate_evidence, run_structured_model, user_templates, validate_model_capability
from jobradar.services.posting_fetch import PART_NAMES, fetch_missing_sources, posting_missing
from jobradar.services.prompt_builder import APPLICATION_REQUIREMENTS_RULES, APPLICATION_REQUIREMENTS_SCHEMA_FIELD, build_candidate_profile_text, user_profile_settings

logger = logging.getLogger(__name__)

# AC4: the owner-visible default for a letter the posting does not mention (or calls optional).
LETTER_RULE = 'Letters the posting does not mention, or calls optional, are not prepared automatically. Generate one from the CV section if you want it.'
LANGUAGE_NAMES = {'en': 'English', 'de': 'German'}
DOCUMENT_NAMES = {'cv': 'CV', 'letter': 'Full letter', 'message': 'Short message'}
WANT = ('required', 'preferred')
FULL_LETTER_TYPES = ('cover_letter', 'motivation_letter')
INTERRUPTED = 'Stopped before it finished (the server restarted). Retry to prepare it again.'
NOT_ANALYSED = 'Application requirements are not analysed yet. Analyse the job, then move it to To apply again or press Prepare.'
ANALYSING = 'Analysing application requirements…'
ANALYSIS_INTERRUPTED = 'Requirements analysis stopped before it finished (the server restarted). Press Prepare to retry.'
CANCELLED = 'Cancelled from the queue. Retry to prepare it again.'
FILES_EXIST = 'Generated files already exist for this job, so nothing was prepared automatically. Generate more from the CV section.'
PREPARE_STATUSES = ('new', 'reviewed', 'to_apply')  # TASK-312 AC1; a retry also Ready to submit
FINISHED_LIMIT = 50  # TASK-312: finished items the queue lists, newest first
AUTO_RETRIES = 3  # TASK-317: automatic retries of one usage-limited item
REANALYSIS_FAILED = 'Re-analysis failed'  # TASK-319: the prefix of a failed late-text re-analysis's reason
INCOMPLETE = 'Posting incomplete'  # TASK-322: the prefix of _gate's reason for a posting lacking a required part
# TASK-324/325: the automatic pipeline's in-progress stages, as the Queue labels them.
PIPELINE_RUNNING = {'queued': 'Waiting to analyse', 'fetching': 'Fetching posting', 'analysing': 'Analysing fit',
                    'requirements': 'Analysing requirements'}  # 'requirements' is derived in queue_state, never stored
PIPELINE_INTERRUPTED = 'Analysis stopped before it finished (the server restarted). Press Retry.'
DAILY_LIMIT = 'Daily limit of {} automatic runs reached. Press Retry to run it now, or raise the limit on the Profile page.'
CHANGED = 'Posting changed since these documents were made'  # TASK-336: the note documents the owner reviewed keep
REANALYSED = 'Analysed again since these documents were made'  # TASK-337: the same note when only time passed
PRIORITY_ORDER = {'high': 0, 'medium': 1, 'low': 2}
# TASK-340: seconds one automatic analysis takes before any run of it was measured (cv_tasks.measured_seconds
# replaces it from the first recorded run) -- unmeasured guesses; the same model's CV generation call is ~110 s.
ANALYSIS_SECONDS = {'fit': 120, 'requirements': 60}

# ponytail: one process serves generation (threaded runserver); a DB claim if that changes. Re-entrant
# because a task's on_finish can run in the thread that started it (a task that fails at once, tests).
_lock = RLock()
_analysing = set()  # TASK-308: job ids whose requirements analysis is running; guarded by _lock
_piping = set()  # TASK-324: job ids whose pipeline thread is waiting or running; guarded by _lock
# ponytail: one pipeline run at a time across all accounts (the rest wait on this lock, in no strict order),
# so a bulk add of 20 links never starts 20 model processes; a worker pool if 50 a day get too slow.
_pipeline_lock = Lock()
# TASK-312: (job_id, user_id, key) waiting for a slot, front first, and the number of prepared tasks
# started and not yet finished. Guarded by _lock; the sidecar is the durable copy (resume_queue).
# ponytail: "Move to front" lives only here, so after a restart the queue is back in queued_at order.
_queue = []
_running = 0
_timer = None  # TASK-317: (when, Timer) of the next retry_due wake-up; guarded by _lock

_STRING = {'type': 'string'}
# TASK-308: the strict JSON-schema form of APPLICATION_REQUIREMENTS_SCHEMA_FIELD, so structured output
# returns exactly the shape normalize_application_requirements reads.
REQUIREMENTS_SCHEMA = {'type': 'object', 'additionalProperties': False, 'required': ['application_requirements'], 'properties': {
    'application_requirements': {
        'type': 'object', 'additionalProperties': False,
        'required': ['posting_language', 'application_language', 'application_language_quote', 'documents'],
        'properties': {
            'posting_language': {'type': 'string', 'enum': list(POSTING_LANGUAGES)},
            'application_language': {'type': 'string', 'enum': ['en', 'de', '']},
            'application_language_quote': _STRING,
            'documents': {'type': 'array', 'items': {
                'type': 'object', 'additionalProperties': False, 'required': ['type', 'name', 'status', 'quote'],
                'properties': {'type': {'type': 'string', 'enum': list(DOCUMENT_TYPES)}, 'name': _STRING,
                               'status': {'type': 'string', 'enum': list(DOCUMENT_STATUSES)}, 'quote': _STRING}}}}}}}


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
        return [], NOT_ANALYSED
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
    prep, missing = _state(job, user), posting_missing(job)
    if missing and not (prep.get('continue_incomplete') or prep.get('variants')):
        # TASK-322: a posting lacking a required part holds documents until the owner pastes it or continues;
        # a job with documents already prepared (a retry) is past that hold.
        return f"{INCOMPLETE}: missing {', '.join(PART_NAMES[part] for part in missing)}. Paste the full posting on the job page, or Continue anyway.", [], '', None
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
    option, effort = cv_default_choice(available_model_options())  # TASK-303 AC1
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


def _now():
    return timezone.now().isoformat()


def _pump():
    """TASK-312 AC2: start queued variants, front first, while a slot is free. Caller holds _lock."""
    while _queue and _running < settings.PREP_QUEUE_CONCURRENCY:
        _start(*_queue.pop(0))


def _start(job_id, user_id, key):
    """Start one queued variant's background task. Caller holds _lock. The slot it takes is given back
    by _finish however the task ends -- cv_tasks._run calls on_finish from its finally, so ready, failed
    and cancelled alike -- or right here when the task cannot start at all."""
    global _running
    job = JobLead.objects.filter(pk=job_id).first()
    user = get_user_model().objects.filter(pk=user_id).first()
    prep = _state(job, user) if job and user else {}
    variants = prep.get('variants') or {}
    variant = variants.get(key)
    if not variant or variant.get('status') != 'queued':
        return  # cancelled, re-prepared or its job deleted while it waited
    document, choice = variant['document'], prep.get('model') or {}
    options = {'short_message': True} if document == 'message' else {}
    if len({item['language'] for item in variants.values()}) > 1:
        options['name_suffix'] = variant['language'].upper()

    def finished(task_id):
        _finish(job_id, user_id, key, task_id)
    _save(job, user_id, lambda prep: prep['variants'][key].update(status='running', task_id='', started_at=_now()))
    _running += 1
    try:
        # Read when it starts, not when it was queued, so a variant that waited uses the current profile.
        profile = user_profile_settings(user)
        context = load_candidate_evidence(build_candidate_profile_text(user), profile.learned_application_preferences, profile.candidate_evidence)
        task_id = cv_tasks.start_cv_task(
            job_id, user_id, context, variant['language'], variant.get('letter_template', ''), document != 'cv',
            choice['provider'], choice['model'], choice['effort'], choice['speed'], create_cv=document == 'cv',
            auto_clipboard=False, generation_options=options, mark_ready=False, on_finish=finished)
    except Exception as exc:  # one variant that cannot start must not stop the others (AC5)
        _running -= 1
        _save(job, user_id, lambda prep, error=str(exc)[:500]: prep['variants'][key].update(status='failed', error=error, finished_at=_now()))
        return

    def running(prep):
        # A fast task can finish before this runs; its recorded outcome wins.
        if prep['variants'][key]['status'] == 'running' and not prep['variants'][key].get('task_id'):
            prep['variants'][key]['task_id'] = task_id
    _save(job, user_id, running)


def _finish(job_id, user_id, key, task_id):
    """A prepared variant's on_finish: record its outcome, give back its slot, start the next."""
    global _running
    with _lock:
        try:
            job = JobLead.objects.filter(pk=job_id).first()
            task = cv_tasks.get_cv_task(task_id, user_id) or {}
            artifacts = task.get('artifacts') or {}
            files = {name: artifacts[name] for name in ('cv_tex', 'cv_pdf', 'letter_tex', 'letter_pdf') if artifacts.get(name)}
            status = task.get('status') if task.get('status') in ('ready', 'cancelled') else 'failed'

            def record(prep):
                variant = prep.get('variants', {}).get(key)
                if variant is None or variant.get('status') not in ('running', 'cancelled') or variant.get('task_id') not in ('', None, task_id):
                    return  # re-queued (retry, restart) meanwhile, or a newer run owns this variant
                error = '' if status == 'ready' else CANCELLED if status == 'cancelled' else task.get('error') or 'Stopped before it finished.'
                reset_at = task.get('reset_at') and datetime.fromisoformat(task['reset_at'])
                variant.update(task_id=task_id, status=status, files=files if status == 'ready' else {}, error=error, finished_at=_now(),
                               retry_at=_retry_at(status == 'failed' and task.get('usage_limit'), reset_at, variant))
            if job:
                _save(job, user_id, record)
        finally:
            _running -= 1
            _pump()


def prepare(job_id, user, retry=False, inline=False):
    """Queue preparation for a New, Reviewed or To-apply job, or with retry, re-queue only its failed
    (or cancelled) variants. TASK-312: variants join the back of the shared queue rather than starting.
    `inline` (TASK-335's daily batch) analyses missing requirements in the calling thread, not a new one.

    Returns the public state, or None when this account/server cannot generate at all. Concurrency
    safe: a second call (a double transition) finds the variants already recorded and starts nothing.
    """
    if not is_cv_owner(user) or not settings.CODEX_CV_WORKSPACE or not Path(settings.CODEX_CV_WORKSPACE).is_dir():
        return None
    job = JobLead.objects.filter(pk=job_id).first()
    if not job:
        return None
    analyse = False
    with _lock:
        state = public_state(job, user)
        # AC1: TASK-312 widened it from To apply to New/Reviewed/To apply (an apply/maybe evaluation
        # queues those); a retry also the Ready to submit it may have moved to. Applied or later never.
        allowed = (*PREPARE_STATUSES, 'ready_to_submit') if retry else PREPARE_STATUSES
        if job.status not in allowed:
            return state
        # TASK-280.3: a failed variant the owner discarded is not wanted, so Retry leaves it alone.
        failed = [variant for variant in state['variants'] if variant['status'] in ('failed', 'cancelled') and variant.get('review') != 'discard']
        if state['variants'] and not (retry and failed):
            return state
        reason, variants, context, choice = _gate(job, user)
        if (reason in ('', NOT_ANALYSED) or reason.startswith(INCOMPLETE)) and not state['variants'] and any(latest_generated_sources(job, user)):
            # AC5: files the owner already generated are theirs; automatic drafts never join or replace them.
            reason = FILES_EXIST
        if reason == NOT_ANALYSED and not state['variants']:
            # TASK-308: analyse the posting ourselves, off this (request) thread; the worker prepares after.
            analyse = job.id not in _analysing
            if analyse:
                _analysing.add(job.id)
                _save(job, user.pk, lambda prep: prep.update(reason=ANALYSING, variants={}, retry_at=None, analysing_at=_now()))
        elif reason:
            if not state['variants']:
                _save(job, user.pk, lambda prep: prep.update(reason=reason, variants={}, retry_at=None))
            return public_state(job, user, reason_override=reason if state['variants'] else None)
        else:
            if state['variants']:
                # AC5: retry targets only failed variants; ready and running ones are left alone.
                wanted = [variant['key'] for variant in failed]
                stored = _state(job, user)['variants']
                variants = [{**stored[key], 'key': key, 'letter_type': ''} for key in wanted]
            queued_at = _now()

            def queue(prep):
                prep.update(reason='', model=choice)
                prep.setdefault('variants', {})
                for variant in variants:
                    prep['variants'][variant['key']] = {'document': variant['document'], 'language': variant['language'],
                                                        'letter_template': variant.get('letter_template', ''),
                                                        'status': 'queued', 'task_id': '', 'error': '', 'files': {},
                                                        'queued_at': queued_at, 'started_at': None, 'finished_at': None}
            _save(job, user.pk, queue)
            _queue.extend((job.id, user.pk, variant['key']) for variant in variants)
            _pump()
    if analyse:
        if inline:
            _analyse_then_prepare(job.id, user.pk, retry)
        else:
            Thread(target=_analyse_then_prepare, args=(job.id, user.pk, retry), daemon=True).start()
    return public_state(job, user)


def _analyse(job):
    """TASK-308: the posting's application requirements from the CV default model, normalised as analysis."""
    option, effort = cv_default_choice(available_model_options())
    if not option:
        raise RuntimeError('No document model is available on this machine')
    provider, model = option['provider'], option['key']
    model_option = validate_model_capability(provider, model, effort, 'normal')
    prompt = ('Read the job posting below and classify how to apply to it. The posting below is the original_source_text; '
              'quote from it.\n\n' + APPLICATION_REQUIREMENTS_RULES
              + '\n\nReturn only a JSON object: {' + APPLICATION_REQUIREMENTS_SCHEMA_FIELD + '}\n\nJob posting:\n' + job.source_text)
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix='dachapply-requirements-') as workdir:
        data = run_structured_model(prompt, REQUIREMENTS_SCHEMA, provider, model, effort, 'normal', workdir=workdir, model_option=model_option)
    requirements = normalize_application_requirements((data or {}).get('application_requirements'), job, source='analysis')
    if not requirements:
        raise RuntimeError('the model returned no application requirements')
    cv_tasks.record_duration('requirements', provider, model, effort, time.monotonic() - started)  # TASK-340
    return requirements


def _analyse_then_prepare(job_id, user_id, retry):
    """TASK-308 worker: analyse, store, then prepare as usual. A failure becomes the panel's reason."""
    close_old_connections()
    try:
        job = JobLead.objects.filter(pk=job_id).first()
        user = get_user_model().objects.filter(pk=user_id).first()
        if not job or not user:
            return
        try:
            requirements = _analyse(job)
        except Exception as exc:  # AC2: the page says why, never a silent stop
            error = str(getattr(exc, 'summary', '') or exc)[:300].rstrip('.')
            with _lock:  # TASK-317: a usage limit is retried automatically once it resets
                _save(job, user_id, lambda prep: prep.update(reason=f'Requirements analysis failed: {error}. Press Prepare to retry.',
                                                             retry_at=_retry_at(getattr(exc, 'usage_limit', False), getattr(exc, 'reset_at', None), prep)))
            return
        job.refresh_from_db()
        if not job.application_requirements:  # AC3: requirements stored meanwhile (an owner edit) win
            job.application_requirements = requirements
            job.save(update_fields=['application_requirements', 'updated_at'])
        prepare(job_id, user, retry)
    except Exception:
        logger.exception('Analysing application requirements for job %s failed', job_id)
    finally:
        with _lock:
            _analysing.discard(job_id)
        close_old_connections()


def prepare_on_to_apply(job_id, user_id):
    """The status-transition (and TASK-312 evaluation-import) hook: never raises, so a generation
    problem cannot fail the status save or the import."""
    try:
        user = get_user_model().objects.filter(pk=user_id).first()
        if user:
            prepare(job_id, user)
    except Exception:
        logger.exception('Preparing application documents for job %s failed', job_id)


def reanalyse_late_text(job, user):
    """TASK-319: a job analysed from its link alone is evaluated again once its posting text arrived,
    off the request thread, so documents follow the real ad and not the blind verdict -- the committed
    evaluation queues them for apply/maybe itself (json_importer.create_evaluation's TASK-312 hook).
    True when that took over from preparing at once; False (REANALYSE_LATE_TEXT off, no earlier
    evaluation, an account that cannot generate) leaves the caller's own path as it was."""
    choice=UserProfile.objects.filter(user=user).values_list('reanalyse_late_text', flat=True).first()  # TASK-321
    if not (settings.REANALYSE_LATE_TEXT if choice is None else choice) or not is_cv_owner(user) or not JobEvaluation.objects.filter(job_id=job.id).exists():
        return False
    # TASK-340 (measured 2026-10-22, job 1533): this ran in its own thread, so the Queue never showed it, the
    # navbar estimate never counted it, and a success left 'Re-analysis failed ... Press Retry' standing. The
    # pipeline shows the stages, clears the reason when it starts, and applies the TASK-338 document rule.
    return start_pipeline(job.id, user, force=True, reanalyse=CHANGED)


def start_pipeline(job_id, user, force=False, reanalyse=''):
    """TASK-324: a job added with a link is fetched, checked and analysed off the request thread with the
    automatic paths' model, and the evaluation is saved at once (a new job has nothing to overwrite); an
    apply/maybe result then queues documents through json_importer.create_evaluation's TASK-312 hook.
    Only for an account that can generate and a job with no evaluation. `force` (the Queue's Retry) runs
    past the daily limit. True when a run was started or is already under way.
    TASK-336/337: `reanalyse` (the note documents the owner reviewed get) analyses a job that has an
    evaluation again, committed; _after_reanalysis then decides what happens to its documents."""
    job = JobLead.objects.filter(pk=job_id).first()
    if not job or not is_cv_owner(user) or not reanalyse and (not job.url or JobEvaluation.objects.filter(job_id=job_id).exists()):
        return False
    if not force:
        limit = user_profile_settings(user).auto_pipeline_daily_limit
        if not limit:
            return False  # 0: automatic runs are off
        # ponytail: counts the jobs this account added today up to this one, not the runs made; a run log
        # if forced, failed or deleted jobs must count differently.
        if JobLead.objects.filter(created_by=user, created_at__date=timezone.localdate(), pk__lte=job_id).count() > limit:
            with _lock:
                _save(job, user.pk, lambda prep: prep.update(pipeline={'stage': 'limit', 'at': _now()}, reason=DAILY_LIMIT.format(limit), retry_at=None))
            return False
    with _lock:
        if job_id in _piping:
            return True
        _piping.add(job_id)
        _save(job, user.pk, lambda prep: prep.update(pipeline={'stage': 'queued', 'at': _now()}, reason='', retry_at=None))
    Thread(target=_pipeline, args=(job_id, user.pk, reanalyse), name='dachapply-pipeline', daemon=True).start()
    return True


def _pipeline(job_id, user_id, reanalyse=''):
    """TASK-324 worker, one run at a time (_pipeline_lock), modelled on _reanalyse: fetch, then the fit
    analysis committed (it reads whatever posting exists; _gate then holds an incomplete one as today).
    Each stage is recorded in prep['pipeline'] for the Queue (TASK-325); a failure becomes the blocked
    reason Retry re-runs, and a usage limit is retried after its reset (TASK-317)."""
    close_old_connections()
    try:
        with _pipeline_lock:
            job = JobLead.objects.filter(pk=job_id).first()
            user = get_user_model().objects.filter(pk=user_id).first()
            if not job or not user:
                return

            def stage(name, **extra):
                _save(job, user_id, lambda prep: prep.update(pipeline={'stage': name, 'at': _now(), **extra}))
            if not reanalyse and JobEvaluation.objects.filter(job_id=job_id).exists():
                _save(job, user_id, lambda prep: prep.pop('pipeline', None))  # analysed by hand while it waited
                return
            before = _outcome(job)  # TASK-338: what a re-analysis is compared with
            try:
                # TASK-340: the run's duration (fetch + analysis) is measured, and its start kept across both stages.
                started, began = time.monotonic(), _now()
                stage('fetching', started=began)
                fetch_missing_sources([job])
                stage('analysing', started=began)
                option, effort = cv_default_choice(available_model_options())
                result = (job_evaluator.evaluate_jobs([job.id], user, option['provider'], option['key'], effort, 'normal', commit=True) if option
                          else {'ok': False, 'errors': ['No document model is available on this machine']})
                if result['ok']:
                    cv_tasks.record_duration('fit', option['provider'], option['key'], effort, time.monotonic() - started)
            except Exception as exc:  # the Queue says why, never a run stuck at Analysing
                logger.exception('The automatic analysis of job %s failed', job_id)
                result = {'ok': False, 'errors': [str(exc) or type(exc).__name__]}
            with _lock:
                if not result['ok']:
                    error = '; '.join(result['errors'])[:300].rstrip('.')
                    # A failed re-analysis says so, so the Queue's Retry analyses it again (TASK-319's path).
                    failed = REANALYSIS_FAILED if reanalyse else 'Analysis failed'
                    _save(job, user_id, lambda prep: prep.update(pipeline={'stage': 'failed', 'at': _now(), 'error': error}, reason=f'{failed}: {error}. Press Retry.',
                                                                 retry_at=_retry_at(result.get('usage_limit'), result.get('reset_at'), prep)))
                elif result['preview'][0]['recommendation'] == 'skip':
                    stage('skipped', recommendation='skip', fit_score=result['preview'][0]['fit_score'])
                else:
                    stage('analysed')  # the documents (or their hold) take over; queue_state lists their requirements analysis
            if reanalyse and result['ok']:
                _after_reanalysis(job, user, result['preview'][0]['recommendation'] == 'skip', reanalyse, before)
    except Exception:
        logger.exception('The automatic pipeline for job %s failed', job_id)
    finally:
        with _lock:
            _piping.discard(job_id)
        close_old_connections()


def _outcome(job):
    """TASK-338: what a re-analysis may change -- the latest recommendation and the requirements' documents."""
    job.refresh_from_db(fields=['application_requirements'])
    return (JobEvaluation.objects.filter(job_id=job.id).order_by('-created_at', '-id').values_list('recommendation', flat=True).first(),
            (job.application_requirements or {}).get('documents') or [])


def _unreviewed(prep):
    return [key for key, variant in (prep.get('variants') or {}).items() if not variant.get('review') and variant.get('status') in ('ready', 'failed', 'cancelled')]


def _after_reanalysis(job, user, skip, note, before):
    """TASK-336/337: what a re-analysis does to the job's documents -- TASK-338: only when something changed,
    the posting (note CHANGED), the recommendation or the requirements' documents; a stale re-check with the
    same outcome leaves documents alone and adds no note. 'Reviewed' is any review mark (keep or discard; a
    selected package is kept, so Ready to submit counts too). A skip stops the documents still queued or
    running and keeps every file. Otherwise kept variants, or files the owner generated, stay with `note`,
    and the unreviewed finished variants are redone (_redo) within today's prepare budget; over it the job
    is marked redo_pending and run_daily redoes it first. Variants still queued or running are left alone.
    ponytail: a running one keeps the text it started from; Retry it by hand if that matters."""
    if note != CHANGED and _outcome(job) == before:
        return
    prep = _state(job, user)
    variants = prep.get('variants') or {}
    if skip:
        for key, variant in variants.items():
            if variant.get('status') in ('queued', 'running'):
                try:
                    queue_action(user, job.id, key, 'cancel')
                except ValueError:
                    pass  # finished or interrupted meanwhile
        return
    if any(variant.get('review') == 'keep' for variant in variants.values()) or (not variants and any(latest_generated_sources(job, user))):
        _save(job, user.pk, lambda prep: prep.update(outdated=note))
    if _unreviewed(prep):
        preps = {other.id: _state(other, user) for other in accessible_jobs(user).only('id')}
        if _left(user_profile_settings(user).daily_prepare_limit, preps, 'auto_prepared_on') == 0:
            _save(job, user.pk, lambda prep: prep.update(redo_pending=True))
        else:
            _redo(job, user)


def _redo(job, user):
    """TASK-336/338: queue each unreviewed finished variant again from the latest analysis (its old files
    stay on disk, the new ones are written beside them), stamped against today's prepare budget. The
    number redone."""
    redo, queued_at = [], _now()

    def change(prep):
        prep.pop('redo_pending', None)
        redo[:] = _unreviewed(prep)  # read again under the sidecar lock: the owner may have reviewed meanwhile
        if redo:
            prep['auto_prepared_on'] = timezone.localdate().isoformat()
        for key in redo:
            prep['variants'][key].update(status='queued', task_id='', error='', files={}, retry_at=None,
                                         queued_at=queued_at, started_at=None, finished_at=None)
    with _lock:
        _save(job, user.pk, change)
        _queue.extend((job.id, user.pk, key) for key in redo)
        _pump()
    return len(redo)


def _left(limit, preps, key):
    """What is left of today's `limit` (None = Unlimited) after the runs the sidecars stamp with today."""
    today = timezone.localdate().isoformat()
    return None if limit is None else max(0, limit - sum(prep.get(key) == today for prep in preps.values()))


def _counted_run(job, user, note):
    """One analysis that counts against today's analysis budget (TASK-335/336/337)."""
    def stamp(prep):
        prep['auto_analysed_on'] = timezone.localdate().isoformat()
        prep.pop('posting_changed', None)
    _save(job, user.pk, stamp)
    start_pipeline(job.id, user, force=True, reanalyse=note)


def reanalyse_changed(job, user):
    """TASK-336: the automatic refresh accepted new text for an open, analysed job -- analyse it again
    through the pipeline, within today's analysis budget (TASK-338: also the owner's Use fetched). Over the
    budget the job is marked, and run_daily takes it first once there is budget again. True only when a
    re-analysis was started, so a caller that would prepare otherwise still does."""
    if job.status not in JobLead.UNAPPLIED_STATUSES or not is_cv_owner(user) or not JobEvaluation.objects.filter(job_id=job.id).exists():
        return False
    preps = {other.id: _state(other, user) for other in accessible_jobs(user).only('id')}
    if _left(user_profile_settings(user).daily_analyse_limit, preps, 'auto_analysed_on') == 0:
        _save(job, user.pk, lambda prep: prep.update(posting_changed=True))
        return False
    _counted_run(job, user, CHANGED)
    return True


def run_daily(user):
    """TASK-335/336/337: spend what is left of today's budgets. Analyses (daily_analyse_limit): first jobs
    whose changed posting waited for budget, then waiting jobs (New/Reviewed/To apply, a link, no
    evaluation) newest first, then open jobs whose latest evaluation is older than reanalyse_after_days,
    oldest first. Documents (daily_prepare_limit): first jobs whose redo waited for budget (TASK-338), then
    New/Reviewed/To apply jobs whose latest evaluation is apply/maybe and that have nothing prepared,
    queued, refused or generated by the owner, highest fit then priority first. Each job is tried at most
    once a day.

    'Today' survives a restart without a column: every run stamps the job's sidecar (auto_analysed_on,
    auto_prepared_on), and a budget is its limit minus today's stamps across the account's jobs.
    ponytail: one sidecar read per job of the account per call (the local loop, every few minutes); a
    counter column if an account grows into thousands of jobs."""
    profile, today = user_profile_settings(user), timezone.localdate().isoformat()
    jobs = list(accessible_jobs(user).defer('raw_description', 'original_source_text', 'pending_source_text'))  # the workers re-read a job
    latest = {row['job_id']: row for row in JobEvaluation.objects.filter(job__in=jobs).order_by('created_at', 'id')
              .values('job_id', 'recommendation', 'fit_score', 'priority', 'created_at')}
    preps = {job.id: _state(job, user) for job in jobs}
    fresh = [job for job in jobs if job.status in JobLead.UNAPPLIED_STATUSES and job.id not in _piping]
    changed = [job for job in fresh if preps[job.id].get('posting_changed') and job.id in latest]
    waiting = sorted((job for job in fresh if job.status in PREPARE_STATUSES and job.url and job.id not in latest),
                     key=lambda job: job.created_at, reverse=True)
    days = profile.reanalyse_after_days
    cutoff = timezone.now() - timedelta(days=days)
    stale = sorted((job for job in fresh if days and job.id in latest and latest[job.id]['created_at'] < cutoff
                    and not preps[job.id].get('posting_changed')), key=lambda job: latest[job.id]['created_at'])
    runs = [(job, note) for group, note in ((changed, CHANGED), (waiting, ''), (stale, REANALYSED))
            for job in group if preps[job.id].get('auto_analysed_on') != today]
    runs = runs[:_left(profile.daily_analyse_limit, preps, 'auto_analysed_on')]
    for job, note in runs:
        _counted_run(job, user, note)
    started = {job.id for job, _ in runs}  # their re-analysis decides about their documents
    documents = sorted((job for job in fresh if job.status in PREPARE_STATUSES and job.id not in started
                        and (latest.get(job.id) or {}).get('recommendation') in ('apply', 'maybe')
                        and not preps[job.id].get('variants') and not preps[job.id].get('reason')
                        and preps[job.id].get('auto_prepared_on') != today and not any(latest_generated_sources(job, user))),
                       key=lambda job: (-latest[job.id]['fit_score'], PRIORITY_ORDER.get(latest[job.id]['priority'], 3)))
    left = _left(profile.daily_prepare_limit, preps, 'auto_prepared_on')
    for job in [job for job in fresh if preps[job.id].get('redo_pending') and job.id not in started][:left]:
        if _redo(job, user) and left is not None:
            left -= 1
    documents = documents[:left]
    for job in documents:
        _save(job, user.pk, lambda prep: prep.update(auto_prepared_on=today))
    if documents:
        Thread(target=_prepare_batch, args=([job.id for job in documents], user.pk), name='dachapply-daily-prepare', daemon=True).start()


def _prepare_batch(job_ids, user_id):
    """TASK-335: one job at a time under _pipeline_lock, so the batch's requirements analyses never run
    beside each other or beside a pipeline analysis."""
    close_old_connections()
    try:
        user = get_user_model().objects.filter(pk=user_id).first()
        for job_id in job_ids:
            with _pipeline_lock:
                prepare(job_id, user, inline=True)
    except Exception:
        logger.exception('The daily document preparation failed')
    finally:
        close_old_connections()


def daily_tick():
    """TASK-335..337: services.mailbox_loop's hook, so the daily budgets are spent only while the local app runs."""
    for user in _owners():
        run_daily(user)


def public_state(job, user, reason_override=None):
    """What the job page shows: each variant with live progress, and interrupted runs as failed.

    TASK-280.3: also each variant's review, adjustment and selection, and the final package; a stale
    package is cleared here so the page says why rather than offering files that are gone.
    """
    state = _state(job, user)
    if state.get('reason') == ANALYSING and job.id not in _analysing:
        state['reason'] = ANALYSIS_INTERRUPTED
    if _stale_reason(state):
        _invalidate(job, user)
        state = _state(job, user)
    selected = (state.get('selection') or {}).get('keys') or []
    variants = []
    for key, stored in (state.get('variants') or {}).items():
        variant = {'key': key, 'review': '', **stored, 'selected': key in selected}
        if variant['status'] in ('queued', 'running'):
            live = cv_tasks.get_cv_task(variant['task_id'], user.pk) if variant['task_id'] else None
            if live:
                variant.update(progress=live['progress'], step_label=live['step_label'], estimated_seconds_remaining=live['estimated_seconds_remaining'])
            elif variant['task_id']:
                variant.update(status='failed', error=INTERRUPTED)
        if variant['status'] == 'ready':
            # TASK-280.3: every file, not any -- a PDF left behind after its TeX was renamed is not the variant.
            variant['missing'] = not _files_present(variant)
        adjust_task = variant.pop('adjust_task_id', '')
        if adjust_task:
            live = cv_tasks.get_cv_task(adjust_task, user.pk)
            if live and live['status'] in ('queued', 'running', 'cancelling'):
                variant.update(adjusting=True, progress=live['progress'], step_label=live['step_label'], estimated_seconds_remaining=live['estimated_seconds_remaining'])
            elif not live:
                variant['adjust_error'] = INTERRUPTED
        variants.append(variant)
    order = {'cv': 0, 'letter': 1, 'message': 2}
    variants.sort(key=lambda variant: (order.get(variant['document'], 3), variant['language']))
    return {'reason': reason_override if reason_override is not None else state.get('reason', ''), 'rule': LETTER_RULE,
            'model': state.get('model') or {}, 'variants': variants, 'selection': selected, 'invalidated': state.get('invalidated', ''),
            'outdated': state.get('outdated', '')}  # TASK-336/337


# --- TASK-280.3: review, final package, independent adjustment, export ----------------------------

def _label(variant):
    return f"{DOCUMENT_NAMES.get(variant.get('document'), 'Document')} · {LANGUAGE_NAMES.get(variant.get('language'), variant.get('language', ''))}"


def _files_present(variant):
    files = variant.get('files') or {}
    return bool(files) and all(Path(path).is_file() for path in files.values())


def _stale_reason(prep):
    """Why the stored final package no longer holds, or ''. Files are compared by path: a deleted,
    renamed (TASK-271) or newly written file is not the document the owner chose."""
    selection = prep.get('selection')
    if not selection:
        return ''
    variants = prep.get('variants') or {}
    current = []
    for key in selection.get('keys') or []:
        variant = variants.get(key)
        if not variant or variant.get('status') != 'ready' or variant.get('review') == 'discard':
            return f'The final package was cleared: {_label(variant or {})} was discarded or is no longer prepared. Select a package again.'
        current += (variant.get('files') or {}).values()
    for path in selection.get('files') or []:
        if not Path(path).is_file():
            return f'The final package was cleared: {Path(path).name} is no longer on disk (deleted or renamed). Select a package again.'
    if sorted(current) != sorted(selection.get('files') or []):
        return 'The final package was cleared: a selected document was written to a new file. Select a package again.'
    return ''


def _unready(job_id):
    # Without a selected package a prepared job is a draft again. The filter is the no-downgrade rule:
    # only Ready to submit moves, never Applied or later -- one conditional UPDATE, like
    # cv_tasks.mark_ready_to_submit, so a status the owner changed meanwhile wins.
    return JobLead.objects.filter(pk=job_id, status='ready_to_submit').update(
        status='to_apply', status_date=None, feedback_due_date=None, last_update_date=None)


def _invalidate(job, user):
    def change(prep):
        reason = _stale_reason(prep)  # re-checked under the sidecar lock: a fresh selection may have won
        if reason:
            prep.pop('selection', None)
            prep['invalidated'] = reason
    _save(job, user.pk, change)
    if not _state(job, user).get('selection'):
        _unready(job.id)


def _required_kinds(job):
    """Documents the posting requires; a package without them is not complete."""
    documents = (job.application_requirements or {}).get('documents') or []
    required = {doc.get('type') for doc in documents if doc.get('status') == 'required'}
    return {kind for kind, types in (('letter', FULL_LETTER_TYPES), ('message', ('short_message',))) if required & set(types)}


def _check_package(job, variants, keys):
    """Raises ValueError unless keys are one coherent, complete package: exactly one CV plus at most one
    full letter and one short message, all ready and not discarded, in one language, files on disk."""
    if not isinstance(keys, list) or not all(isinstance(key, str) for key in keys) or len(set(keys)) != len(keys):
        raise ValueError('Choose the documents of the package.')
    chosen = []
    for key in keys:
        variant = variants.get(key)
        if not variant or variant.get('status') != 'ready':
            raise ValueError('Only prepared documents that are ready can be part of the package.')
        if variant.get('review') == 'discard':
            raise ValueError(f'{_label(variant)} is discarded. Restore it first.')
        if not _files_present(variant):
            raise ValueError(f'{_label(variant)} is no longer on disk.')
        chosen.append(variant)
    documents = [variant['document'] for variant in chosen]
    if documents.count('cv') != 1:
        raise ValueError('A package has exactly one CV.')
    if len(documents) != len(set(documents)):
        raise ValueError('A package has at most one full letter and one short message.')
    if len({variant['language'] for variant in chosen}) != 1:
        raise ValueError('All documents of a package must be in the same language.')
    missing = _required_kinds(job) - set(documents)
    if missing:
        raise ValueError('The posting requires a ' + ' and a '.join(DOCUMENT_NAMES[kind].lower() for kind in sorted(missing)) + '; add it to the package.')


def review(job, user, action, key='', keys=None):
    """keep / discard / restore one variant, select the final package, or clear it. Raises ValueError.

    Discard never deletes a file, so restore works while the files still exist. Selecting a complete
    package is the only way a prepared job reaches Ready to submit (mark_ready_to_submit never moves
    Applied or later); clearing the package makes it a draft again.
    """
    if action not in ('keep', 'discard', 'restore', 'select', 'clear'):
        raise ValueError('Unknown action.')

    def change(prep):  # validated under the sidecar lock, so a check and its write cannot interleave
        variants = prep.get('variants') or {}
        if action in ('keep', 'select'):
            prep.pop('outdated', None)  # TASK-336: the owner approved documents again after the change
        if action == 'select':
            _check_package(job, variants, keys)
            for chosen in keys:
                variants[chosen]['review'] = 'keep'
            prep['selection'] = {'keys': keys, 'files': [path for chosen in keys for path in variants[chosen]['files'].values()]}
            prep.pop('invalidated', None)
        elif action == 'clear':
            prep.pop('selection', None)
            prep.pop('invalidated', None)
        elif key not in variants:
            raise ValueError('That document was not prepared for this job.')
        elif action == 'discard':
            variants[key]['review'] = 'discard'
        elif variants[key].get('status') != 'ready' or not _files_present(variants[key]):
            raise ValueError(f'{_label(variants[key])} has no files on disk, so it cannot be kept or restored.')
        else:
            variants[key]['review'] = 'keep'
    _save(job, user.pk, change)
    if action == 'select':
        cv_tasks.mark_ready_to_submit(job.id, respect_skip=False)  # TASK-310: the owner's explicit choice wins over 'skip'
    elif action == 'clear':
        _unready(job.id)
    return public_state(job, user)


def adjust(job, user, key, instructions, choice=None):
    """Readjust ONE variant through the existing revision path (start_cv_task with that variant's own
    source files, as start_cv_revision does): the revision rewrites only those files, so every other
    variant stays byte-identical. Raises ValueError (bad request) or RuntimeError (unavailable)."""
    instructions = (instructions or '').strip()
    if not instructions:
        raise ValueError('Describe the adjustment.')
    variant = next((item for item in public_state(job, user)['variants'] if item['key'] == key), None)
    if not variant or variant['status'] != 'ready' or variant.get('missing'):
        raise ValueError('Only a ready document whose files are on disk can be adjusted.')
    if variant['review'] == 'discard':
        raise ValueError(f'{_label(variant)} is discarded. Restore it first.')
    if variant.get('adjusting'):
        raise ValueError(f'{_label(variant)} is already being adjusted.')
    stored = _state(job, user).get('model') or {}
    choice = {field: (choice or {}).get(field) or stored.get(field) or default
              for field, default in (('provider', ''), ('model', ''), ('effort', ''), ('speed', 'normal'))}
    validate_model_capability(*choice.values(), needs_tools=True)
    profile = user_profile_settings(user)
    context = load_candidate_evidence(build_candidate_profile_text(user), profile.learned_application_preferences, profile.candidate_evidence)
    document, files = variant['document'], variant['files']

    def finished(task_id):
        _adjusted(job.id, user.pk, key, task_id)
    task_id = cv_tasks.start_cv_task(
        job.id, user.pk, context, variant['language'], variant.get('letter_template', ''), document != 'cv',
        choice['provider'], choice['model'], choice['effort'], choice['speed'],
        source_cv=files.get('cv_tex'), source_letter=files.get('letter_tex'), revision_instructions=instructions[:5000],
        create_cv=document == 'cv', auto_clipboard=False,
        # short_message keeps a message's sidecar pointer apart from the full letter (TASK-280.2).
        generation_options={'short_message': True} if document == 'message' else None, mark_ready=False, on_finish=finished)
    live = cv_tasks.get_cv_task(task_id, user.pk)
    if live and live['status'] not in ('ready', 'failed', 'cancelled'):  # a fast task already recorded its outcome
        _save(job, user.pk, lambda prep: prep['variants'][key].update(adjust_task_id=task_id, adjust_error=''))
    return public_state(job, user)


def _adjusted(job_id, user_id, key, task_id):
    job = JobLead.objects.filter(pk=job_id).first()
    task = cv_tasks.get_cv_task(task_id, user_id) or {}
    if not job:
        return
    artifacts = task.get('artifacts') or {}
    files = {name: artifacts[name] for name in ('cv_tex', 'cv_pdf', 'letter_tex', 'letter_pdf') if artifacts.get(name)}

    def record(prep):
        variant = prep.get('variants', {}).get(key)
        if variant is None:
            return
        variant.pop('adjust_task_id', None)
        if task.get('status') == 'ready' and files:
            variant.update(files=files, adjust_error='')
        else:
            # A failed adjustment keeps the variant's previous files and state.
            variant['adjust_error'] = task.get('error') or 'Stopped before it finished.'
    _save(job, user_id, record)


def export_variants(job, user, key=''):
    """The variant named by key, or with no key the selected final package. Raises ValueError."""
    state = public_state(job, user)
    variants = {variant['key']: variant for variant in state['variants']}
    keys = [key] if key else state['selection']
    if not keys:
        raise ValueError(state['invalidated'] or 'Select a final package first.')
    chosen = [variants.get(item) for item in keys]
    if not all(variant and variant['status'] == 'ready' and not variant.get('missing') for variant in chosen):
        raise ValueError('That document has no files on disk.')
    return chosen


def export_name(variant, path):
    """The file's own name, with its language added when the name does not carry it already."""
    path = Path(path)
    language = variant['language'].upper()
    stem = path.stem if re.search(rf'-{language}(?:-\d+)?$', path.stem) else f'{path.stem}-{language}'
    return stem + path.suffix


def copy_text(job, variants):
    """TeX to paste, in cv_tasks._clipboard_payload's format (which knows one CV and one letter only):
    the original-posting link as a TeX comment, then each document under its meaningful name."""
    texts = [(export_name(variant, path), Path(path).read_text(encoding='utf-8'))
             for variant in variants for kind, path in variant['files'].items() if kind.endswith('_tex')]
    body = texts[0][1] if len(texts) == 1 else '\n\n'.join(f'% ===== {name} =====\n{text}' for name, text in texts)
    url = ' '.join((job.url or '').split())
    return f'% Job listing: {url}\n\n{body}' if url else body


def package_zip(job, user, variants, single):
    """(bytes, filename): every TeX and PDF under its meaningful name, plus a link to the posting."""
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as bundle:
        for variant in variants:
            for path in variant['files'].values():
                bundle.write(path, export_name(variant, path))
        url = ' '.join((job.url or '').split())
        if url:
            bundle.writestr('Original-Posting.url', f'[InternetShortcut]\r\nURL={url}\r\n')
    if single:
        filename = Path(export_name(variants[0], next(iter(variants[0]['files'].values())))).stem + '.zip'
    else:
        filename = f"{Path(_package_filename(job, applicant_name(user))).stem}-{variants[0]['language'].upper()}.zip"
    return archive.getvalue(), filename


def board_summary(job, user):
    """TASK-299: {running, done, failed, progress, eta} for a board badge, or None without a preparation.

    Read-only and cheap (one sidecar read, in-memory task lookups): unlike public_state it never
    clears a stale package, so a board poll writes nothing. Discarded variants are not counted;
    progress is the mean over the variants still running (100 once none are), and eta the slowest
    running variant's estimated_seconds_remaining, since the package is ready only when that one is.
    """
    running = done = failed = 0
    progress, eta = [], 0
    for variant in (_state(job, user).get('variants') or {}).values():
        if variant.get('review') == 'discard':
            continue
        if variant.get('status') in ('queued', 'running'):
            live = cv_tasks.get_cv_task(variant['task_id'], user.pk) if variant.get('task_id') else None
            if live or not variant.get('task_id'):
                running += 1
                progress.append(live['progress'] if live else 0)
                eta = max(eta, (live or {}).get('estimated_seconds_remaining') or 0)
            else:
                failed += 1  # interrupted by a restart, as public_state reports it
        elif variant.get('status') == 'ready':
            done += 1
        else:
            failed += 1
    if not running + done + failed:
        return None
    return {'running': running, 'done': done, 'failed': failed, 'progress': round(sum(progress) / len(progress)) if progress else 100, 'eta': eta}


# --- TASK-312: the queue page, its actions, and resuming after a restart ------------------------

def _live(variant, user):
    """(status, error, live task) as the queue shows a stored variant: queued or running with a task
    that is gone was interrupted by a restart, so it shows failed, as public_state reports it."""
    status, task_id = variant.get('status'), variant.get('task_id')
    if status not in ('queued', 'running') or not task_id:
        return status, variant.get('error', ''), None
    live = cv_tasks.get_cv_task(task_id, user.pk)
    return (status, variant.get('error', ''), live) if live else ('failed', INTERRUPTED, None)


def queue_state(user):
    """AC4: every prepared variant of the owner's unapplied jobs except discarded ones -- running, then
    queued by position, then (TASK-313) jobs whose preparation was refused, then the newest
    FINISHED_LIMIT finished ones. Read-only, like board_summary. TASK-340: each running or queued item's
    eta_seconds is when it should finish, from measured durations, and 'summary' is {done (ready or skipped today),
    total, analyses_left, documents_left, seconds_left} for the navbar.

    ponytail: one sidecar read per unapplied job per poll, as application_prep_active does; an index
    of jobs with a preparation if the board grows into thousands of open jobs.
    """
    with _lock:
        positions = {entry: index for index, entry in enumerate(_queue, 1)}
    expected = {route: cv_tasks.measured_seconds(route) or seconds for route, seconds in ANALYSIS_SECONDS.items()}
    items, blocked, fits, requirements = [], [], [], []
    today, done = timezone.localdate(), 0
    for job in accessible_jobs(user).filter(status__in=JobLead.UNAPPLIED_STATUSES).only('id', 'company', 'title', 'status', 'source_fetch_error'):
        prep = _state(job, user)
        done += _done_today(prep, today)
        if prep.get('reason') and not prep.get('variants') and prep['reason'] not in (ANALYSING, FILES_EXIST):
            # TASK-313 AC2: a job whose preparation was refused shows why, instead of vanishing. TASK-318: a
            # missing text says why its link could not be read (e.g. the paste hint), the _gate wording otherwise.
            error = job.source_fetch_error if prep['reason'] == 'The job has no usable posting text yet.' and job.source_fetch_error else prep['reason']
            blocked.append({'job_id': job.id, 'company': job.company, 'title': job.title, 'job_status': job.status, 'key': '',
                            'label': 'Documents', 'document': None, 'language': None, 'status': 'blocked', 'position': None,
                            'progress': 0, 'eta_seconds': None, 'error': error, 'files': [],
                            'queued_at': None, 'started_at': None, 'finished_at': None, 'retry_at': prep.get('retry_at'),
                            'incomplete': prep['reason'].startswith(INCOMPLETE)})  # TASK-322: offers Continue anyway
        pipeline = prep.get('pipeline') or {}
        # An analysed job stays listed while its application requirements are analysed (TASK-308) -- TASK-340: only
        # while that run is alive (public_state's test), so one a restart stopped never shows as running, and not
        # over a fit analysis queued or running again for the job, which stays in the fit lane.
        stage = pipeline.get('stage')
        if job.id in _analysing and stage not in PIPELINE_RUNNING:
            stage = 'requirements'
        # TASK-336/337: a re-analysis under way also shows beside the job's documents.
        if (stage in PIPELINE_RUNNING or stage == 'skipped') and (not prep.get('variants') or stage in PIPELINE_RUNNING and job.id in _piping):
            # TASK-325: the automatic pipeline's step -- running, or finished as a skip; limit and failed are
            # blocked above through prep['reason']. Variants replace it (the documents' own rows).
            skipped = stage == 'skipped'  # TASK-344: not `done`, which is the summary's counter
            item = {'job_id': job.id, 'company': job.company, 'title': job.title, 'job_status': job.status, 'key': '',
                    'label': 'Not applying' if skipped else PIPELINE_RUNNING[stage], 'document': None, 'language': None,
                    'status': 'skipped' if skipped else 'running', 'position': None, 'progress': 0, 'eta_seconds': None,
                    'error': f"Skip · fit {pipeline.get('fit_score')}" if skipped else '', 'files': [], 'queued_at': None,
                    'started_at': pipeline.get('at'), 'finished_at': pipeline.get('at') if skipped else None, 'retry_at': None, 'incomplete': False}
            items.append(item)
            # TASK-340: eta_seconds is the run's expected duration here (what is left of it once running); _schedule
            # turns the fit analyses' into finish times. A requirements analysis runs in a thread of its own.
            if stage == 'requirements':
                item['eta_seconds'] = round(max(0, expected['requirements'] - _elapsed(prep.get('analysing_at') or pipeline.get('at'))))
                requirements.append(item)
            elif not skipped:
                # The run's start (fetch included); a sidecar from before TASK-340 has only the stage's.
                item['eta_seconds'] = expected['fit'] - (0 if stage == 'queued' else _elapsed(pipeline.get('started') or pipeline.get('at')))
                fits.append((stage == 'queued', pipeline.get('at') or '', item))
        for key, variant in (prep.get('variants') or {}).items():
            if variant.get('review') == 'discard':
                continue
            status, error, live = _live(variant, user)
            items.append({'job_id': job.id, 'company': job.company, 'title': job.title, 'job_status': job.status, 'key': key,
                          'label': _label(variant), 'document': variant.get('document'), 'language': variant.get('language'),
                          'status': status, 'position': positions.get((job.id, user.pk, key)) if status == 'queued' else None,
                          'progress': 100 if status == 'ready' else round(live['progress']) if live else 0,
                          'eta_seconds': live['estimated_seconds_remaining'] if live else _document_seconds(prep, variant) if status == 'queued' else None, 'error': error,
                          'files': [Path(path).name for path in (variant.get('files') or {}).values()],
                          'queued_at': variant.get('queued_at'), 'started_at': variant.get('started_at'), 'finished_at': variant.get('finished_at'),
                          'retry_at': variant.get('retry_at') if variant.get('status') == 'failed' else None, 'incomplete': False})
    running = sorted((item for item in items if item['status'] == 'running'), key=lambda item: item['started_at'] or '')
    queued = sorted((item for item in items if item['status'] == 'queued'), key=lambda item: (item['position'] is None, item['position'] or 0, item['queued_at'] or ''))
    finished = sorted((item for item in items if item['status'] not in ('running', 'queued')), key=lambda item: item['finished_at'] or '', reverse=True)
    # TASK-340: the lanes run side by side, so the time left is the latest one's end: fit analyses one at a time
    # under _pipeline_lock (the one holding it first, then the waiting ones as queued -- the lock keeps no strict
    # order); each requirements analysis in its own thread (a pipeline job's runs beside the next fit; the daily
    # batch's holds the lock, so a fit waiting behind it ends up to one requirements analysis later than shown);
    # documents PREP_QUEUE_CONCURRENCY at a time in queue order, independent of the lock.
    # ponytail: documents an analysis will yield are unknown until it ends, so they are not counted yet.
    fits.sort(key=lambda fit: fit[:2])
    documents = [item for item in running + queued if item['document']]
    lanes = [_schedule([item for *_, item in fits], 1), _schedule(documents, settings.PREP_QUEUE_CONCURRENCY),
             *(item['eta_seconds'] for item in requirements)]
    # A job moved past To apply today left the list above, but what was done for it today still counts.
    for job in accessible_jobs(user).exclude(status__in=JobLead.UNAPPLIED_STATUSES).filter(updated_at__date=today).only('id'):
        done += _done_today(_state(job, user), today)
    pending = len(running) + len(queued)
    summary = {'done': done, 'total': done + pending, 'analyses_left': pending - len(documents), 'documents_left': len(documents),
               'seconds_left': round(max(lanes, default=0))}
    return {'concurrency': settings.PREP_QUEUE_CONCURRENCY, 'summary': summary, 'items': running + queued + blocked + finished[:FINISHED_LIMIT]}


def _done_today(prep, today):
    """TASK-340: how many of a job's items the Queue page lists under Done finished today -- ready documents,
    or the pipeline's skip. Failed and cancelled are not done."""
    pipeline, variants = prep.get('pipeline') or {}, prep.get('variants') or {}
    stamps = [variant.get('finished_at') for variant in variants.values() if variant.get('status') == 'ready' and variant.get('review') != 'discard']
    if pipeline.get('stage') == 'skipped' and not variants:
        stamps.append(pipeline.get('at'))
    return sum(1 for iso in stamps if (when := _when(iso)) and timezone.localdate(when) == today)


def _when(iso):
    """An aware datetime from a stored ISO stamp, or None."""
    try:
        value = datetime.fromisoformat(iso)
    except (TypeError, ValueError):
        return None
    return value if timezone.is_aware(value) else None


def _elapsed(iso):
    since = _when(iso)
    return max(0, (timezone.now() - since).total_seconds()) if since else 0


def _document_seconds(prep, variant):
    """TASK-340: a queued variant's expected duration from cv_tasks' measured timing for the model it will run with."""
    choice, document = prep.get('model') or {}, variant.get('document')
    return cv_tasks.estimate_seconds(choice.get('provider'), choice.get('model'), choice.get('effort'), choice.get('speed') or 'normal',
                                     create_cv=document == 'cv', create_letter=document != 'cv')['seconds']


def _schedule(items, slots):
    """TASK-340: items run `slots` at a time in this order, each for its eta_seconds (a running one's: what is
    left); each eta_seconds becomes when that item finishes, from now. Returns when the last one does."""
    free = [0] * slots
    for item in items:
        end = heapq.heappop(free) + max(0, item['eta_seconds'] or 0)
        item['eta_seconds'] = round(end)
        heapq.heappush(free, end)
    return max(free)


def queue_action(user, job_id, key, action):
    """AC5: cancel (queued or running; a running one's task is stopped), retry (failed or cancelled, to
    the back of the queue) or first (queued, to the front). TASK-322: continue (key '', a job blocked as
    Posting incomplete) prepares despite the gaps and remembers that for the job. Raises ValueError;
    returns queue_state."""
    if action not in ('cancel', 'retry', 'first', 'continue'):
        raise ValueError('Unknown action.')
    try:
        job = accessible_jobs(user).filter(pk=int(job_id), status__in=JobLead.UNAPPLIED_STATUSES).first()
    except (TypeError, ValueError):
        job = None
    prep = _state(job, user) if job and key == '' and action in ('retry', 'continue') else {}
    if (action == 'retry' and (prep.get('pipeline') or {}).get('stage') in ('limit', 'failed') and not prep.get('variants')
            and not JobEvaluation.objects.filter(job_id=job.id).exists()):
        # TASK-324: a pipeline run held by the daily limit or failed runs again now, past the limit (retry_due too).
        start_pipeline(job.id, user, force=True)
        return queue_state(user)
    if action == 'continue':
        if prep.get('variants') or not (prep.get('reason') or '').startswith(INCOMPLETE):
            raise ValueError('Only a job held as Posting incomplete can be continued.')
        _save(job, user.pk, lambda prep: prep.update(continue_incomplete=True))
        prepare(job.id, user)
        return queue_state(user)
    if prep.get('reason') and not prep.get('variants'):
        # TASK-313 AC3: a blocked job -- read its posting (network, so outside _lock), then gate again.
        # TASK-319: a posting that just replaced its link (or a failed or running re-analysis) is analysed
        # again first; the re-analysis prepares, not this.
        before = job.source_text
        fetch_missing_sources([job])
        late = job.source_text != before or prep['reason'].startswith(REANALYSIS_FAILED) or job.id in _piping
        if not (late and reanalyse_late_text(job, user)):
            prepare(job.id, user)
        return queue_state(user)
    with _lock:
        variant = (_state(job, user).get('variants') or {}).get(key) if job else None
        if not variant or variant.get('review') == 'discard':
            raise ValueError('That document is not in the queue.')
        status, entry = _live(variant, user)[0], (job.id, user.pk, key)
        if action == 'cancel':
            if status not in ('queued', 'running'):
                raise ValueError(f'{_label(variant)} is {status}; only a queued or running document can be cancelled.')
            if entry in _queue:
                _queue.remove(entry)
            _save(job, user.pk, lambda prep: prep['variants'][key].update(status='cancelled', error=CANCELLED, finished_at=_now()))
            if status == 'running' and variant.get('task_id'):
                # Its slot is given back when the task's thread actually stops (_finish), not now.
                cv_tasks.cancel_cv_task(variant['task_id'], user.pk)
        elif action == 'retry':
            if status not in ('failed', 'cancelled'):
                raise ValueError(f'{_label(variant)} is {status}; only a failed or cancelled document can be retried.')
            _save(job, user.pk, lambda prep: prep['variants'][key].update(status='queued', task_id='', error='', files={},
                                                                          queued_at=_now(), started_at=None, finished_at=None))
            _queue.append(entry)
            _pump()
        else:
            if status != 'queued':
                raise ValueError(f'{_label(variant)} is {status}; only a queued document can be moved to the front.')
            if entry in _queue:
                _queue.remove(entry)
            _queue.insert(0, entry)
            _pump()
    return queue_state(user)


def _owners():
    """The accounts that may generate. The sidecar path is a hash of user and job, so a scan of the
    sidecars starts from them and their unapplied jobs in the database, not a directory listing."""
    owner = (settings.CODEX_CV_OWNER_EMAIL or '').strip()
    match = Q(jobradar_profile__can_generate_cv=True)
    if owner:
        match |= Q(email__iexact=owner) | Q(username__iexact=owner)
    return [user for user in get_user_model().objects.filter(match).distinct() if is_cv_owner(user)]


def resume_queue():
    """AC3: re-queue, in queued_at order, every variant a restart left queued, or running with no live
    task (the owners' unapplied jobs, _owners). A re-queued variant is plain queued again (task_id
    cleared), so public_state and board_summary stop reporting it as interrupted. TASK-317: then
    retry_due, so usage-limit retries recorded before the restart are scheduled again."""
    with _lock:
        found = []
        for user in _owners():
            for job in accessible_jobs(user).filter(status__in=JobLead.UNAPPLIED_STATUSES).only('id'):
                prep = _state(job, user)
                if (prep.get('pipeline') or {}).get('stage') in PIPELINE_RUNNING and job.id not in _piping:
                    # TASK-324: a pipeline run the restart stopped is blocked with Retry, never left "running".
                    _save(job, user.pk, lambda prep: prep.update(pipeline={'stage': 'failed', 'at': _now(), 'error': PIPELINE_INTERRUPTED},
                                                                 reason=PIPELINE_INTERRUPTED, retry_at=None))
                for key, variant in (prep.get('variants') or {}).items():
                    task_id = variant.get('task_id')
                    left = variant.get('status') == 'queued' or (variant.get('status') == 'running' and not (task_id and cv_tasks.get_cv_task(task_id, user.pk)))
                    if left and (job.id, user.pk, key) not in _queue:
                        found.append((variant.get('queued_at') or '', job, user, key))
        for _, job, user, key in sorted(found, key=lambda item: item[0]):
            _save(job, user.pk, lambda prep, key=key: prep['variants'][key].update(status='queued', task_id='', started_at=None))
            _queue.append((job.id, user.pk, key))
        _pump()
    retry_due()
    return len(found)


# --- TASK-317: automatic retry after a usage limit ----------------------------------------------

def _retry_at(usage_limit, reset_at, item):
    """When a usage-limit failure is retried automatically (ISO), arming the timer for it; None for any
    other failure or once `item` spent its AUTO_RETRIES. Caller holds _lock."""
    if not usage_limit or item.get('auto_retries', 0) >= AUTO_RETRIES:
        return None
    when = reset_at + timedelta(minutes=1) if reset_at else timezone.now() + timedelta(minutes=30)
    _arm(when)
    return when.isoformat()


def _arm(when):
    """Wake retry_due at `when`, unless the one timer already wakes sooner. Caller holds _lock."""
    global _timer
    if _timer and _timer[0] <= when:
        return
    if _timer:
        _timer[1].cancel()
    _timer = (when, Timer(max(0, (when - timezone.now()).total_seconds()), _retry_worker))
    _timer[1].daemon = True
    _timer[1].start()


def retry_due():
    """Re-queue, through queue_action's own retry, every usage-limited failure whose retry_at passed --
    a failed variant, or a preparation whose requirements analysis hit the limit -- and arm the timer
    for the next one. The sidecars are the truth, so a retry the owner already made is not repeated."""
    global _timer
    now, due, later = timezone.now(), [], []
    with _lock:
        if _timer:
            _timer[1].cancel()
            _timer = None
        for user in _owners():
            for job in accessible_jobs(user).filter(status__in=JobLead.UNAPPLIED_STATUSES).only('id'):
                prep = _state(job, user)
                variants = prep.get('variants') or {}
                pending = [(key, variant) for key, variant in variants.items() if variant.get('status') == 'failed'] if variants else [('', prep)]
                for key, item in pending:
                    if item.get('retry_at'):
                        when = datetime.fromisoformat(item['retry_at'])
                        if when <= now:
                            due.append((job, user, key))
                        else:
                            later.append(when)
        for job, user, key in due:
            def spend(prep, key=key):
                item = prep['variants'][key] if key else prep
                item.update(retry_at=None, auto_retries=item.get('auto_retries', 0) + 1)
            _save(job, user.pk, spend)
        if later:
            _arm(min(later))
    for job, user, key in due:  # outside _lock: a blocked job's retry reads its posting first
        try:
            queue_action(user, job.id, key, 'retry')
        except ValueError:
            pass  # cancelled, discarded or moved past To apply meanwhile
    return len(due)


def _retry_worker():
    close_old_connections()
    try:
        retry_due()
    except Exception:
        logger.exception('Retrying usage-limited document preparation failed')
    finally:
        close_old_connections()


def _resume_worker():
    close_old_connections()
    try:
        resume_queue()
    except Exception:
        logger.exception('Resuming the document preparation queue failed')
    finally:
        close_old_connections()


def start_queue_resume():
    """AC3, from AppConfig.ready: only in the serving process (the local mailbox loop's guard; disable
    with DACHAPPLY_PREP_QUEUE_RESUME=0), and off the startup thread, which must not query the database."""
    from jobradar.services.demo_scheduler import should_start_local_loop  # pulls in the digest mailer
    if not should_start_local_loop('DACHAPPLY_PREP_QUEUE_RESUME'):
        return False
    Thread(target=_resume_worker, name='dachapply-prep-queue-resume', daemon=True).start()
    return True
