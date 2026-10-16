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
"""
import io
import logging
import re
import zipfile
from pathlib import Path
from threading import Lock

from django.conf import settings
from django.contrib.auth import get_user_model

from jobradar.models import JobLead
from jobradar.services import cv_tasks
from jobradar.services.cv_generator import _edit_sidecar, _package_filename, _read_artifact_metadata, applicant_name, available_model_options, cv_default_choice, is_cv_owner, latest_generated_sources, load_candidate_evidence, user_templates, validate_model_capability
from jobradar.services.prompt_builder import build_candidate_profile_text, user_profile_settings

logger = logging.getLogger(__name__)

# AC4: the owner-visible default for a letter the posting does not mention (or calls optional).
LETTER_RULE = 'Letters the posting does not mention, or calls optional, are not prepared automatically. Generate one from the CV section if you want it.'
LANGUAGE_NAMES = {'en': 'English', 'de': 'German'}
DOCUMENT_NAMES = {'cv': 'CV', 'letter': 'Full letter', 'message': 'Short message'}
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
        # TASK-280.3: a failed variant the owner discarded is not wanted, so Retry leaves it alone.
        failed = [variant for variant in state['variants'] if variant['status'] == 'failed' and variant.get('review') != 'discard']
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
    """What the job page shows: each variant with live progress, and interrupted runs as failed.

    TASK-280.3: also each variant's review, adjustment and selection, and the final package; a stale
    package is cleared here so the page says why rather than offering files that are gone.
    """
    state = _state(job, user)
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
            'model': state.get('model') or {}, 'variants': variants, 'selection': selected, 'invalidated': state.get('invalidated', '')}


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
        cv_tasks.mark_ready_to_submit(job.id)
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
