import json
import logging
import math
import os
import time
import uuid
import zipfile
from io import BytesIO
from pathlib import Path
from statistics import median
from threading import Event, Lock, Thread

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import close_old_connections
from django.db.models import OuterRef, Q, Subquery

from jobradar.models import ApplicationNote, JobEvaluation, JobLead, UserProfile
from jobradar.services.cv_generator import GenerationCancelled, RecoverableGenerationError, _artifact_metadata_path, _filename_label, _is_sent, _letter_label, _sent_paths, applicant_name, generate_cv_package, latest_generated_sources, preference_exclusion, preferred_names, read_revision_sources, recompile_generated_package, rename_generated_artifact
from jobradar.services.literal_edits import NotLiteral, gate_literal_edits, literal_report, translate_literal_edits
from jobradar.services.posting_fetch import fetch_posting_text


logger=logging.getLogger(__name__)

_tasks={}
_stage_history={}
_lock=Lock()

BASE_TEMPLATE_NOTE_PREFIX='Base templates used: '


def _normalise_base_templates(value):
    if not isinstance(value,dict):
        return {}
    result={}
    for kind in ('cv','letter'):
        names=value.get(kind)
        if isinstance(names,list):
            names=list(dict.fromkeys(name for name in names if isinstance(name,str) and name))
            if names:
                result[kind]=names
    return result


def _latest_base_templates(job):
    for note in job.notes.filter(note_type='cv_change',note__startswith=BASE_TEMPLATE_NOTE_PREFIX):
        try:
            value=json.loads(note.note[len(BASE_TEMPLATE_NOTE_PREFIX):])
        except json.JSONDecodeError:
            continue
        if isinstance(value,dict):
            return _normalise_base_templates(value)
    return {}


def _record_base_templates(job, value):
    ApplicationNote.objects.create(job=job,note_type='cv_change',note=BASE_TEMPLATE_NOTE_PREFIX+json.dumps(
        _normalise_base_templates(value),ensure_ascii=False,separators=(',',':'),sort_keys=True))


_STAGE_CAPS={'queued':0,'preparing':9.5,'generating':64.5,'generated':69.5,'compiling_cv':81.5,'cv_compiled':84.5,'compiling_letter':94.5,'letter_compiled':96.5,'saving':99}


def _stage_key(stage):
    value=(stage or '').lower()
    if value == 'queued': return 'queued'
    if value == 'preparing templates': return 'preparing'
    if value.startswith(('generating ','repairing ')): return 'generating'
    if value.endswith(' generated'): return 'generated'
    if value == 'compiling cv': return 'compiling_cv'
    if value == 'cv compiled': return 'cv_compiled'
    if value == 'compiling motivation letter': return 'compiling_letter'
    if value == 'motivation letter compiled': return 'letter_compiled'
    if value == 'using saved package': return 'cached'
    if value == 'saving files': return 'saving'
    if value in ('cancelling','cancelled'): return value
    if value == 'ready': return 'ready'
    return 'working'


# User-facing step grouping: several raw stage_keys (begin/end markers) collapse into one step.
_STEP_STAGES={'preparing':['preparing'],'generating':['generating','generated'],'compiling_cv':['compiling_cv','cv_compiled'],'compiling_letter':['compiling_letter','letter_compiled'],'cached':['cached'],'saving':['saving']}
_STEP_LABELS={'preparing':'Preparing templates','generating':'Generating documents','compiling_cv':'Compiling CV','compiling_letter':'Compiling motivation letter','cached':'Using saved package','saving':'Saving files'}
# Shown once a step's terminal marker fires, so the UI says the PDF compiled instead of still "Compiling".
_STEP_DONE_LABELS={'generating':'Documents generated','compiling_cv':'CV compiled','compiling_letter':'Motivation letter compiled'}
_STAGE_STEP={stage:step for step,stages in _STEP_STAGES.items() for stage in stages}
_ACTIVE_STAGES={'generating','compiling_cv','compiling_letter'}


def _plan_steps(plan):
    steps=[]
    for key in plan:
        step=_STAGE_STEP.get(key)
        if step and (not steps or steps[-1] != step):
            steps.append(step)
    return steps


def _step_progress(task):
    steps=_plan_steps(task.get('_stage_plan') or [])
    total=len(steps)
    if task['status'] == 'ready':
        return total,total,'Ready'
    stage_key=task.get('_stage_key')
    step=_STAGE_STEP.get(stage_key)
    if step not in steps:
        return 0,total,_STEP_LABELS.get(step, task.get('stage','Preparing'))
    index=steps.index(step)
    members=_STEP_STAGES[step]
    done=len(members) > 1 and stage_key == members[-1]
    return (index+1 if done else index),total,(_STEP_DONE_LABELS.get(step) if done else None) or _STEP_LABELS[step]


def _task_timing(provider, model, effort, speed, create_cv, create_letter, is_revision):
    # ponytail: recalibrated 2026-08-15 against six live runs recorded in cv-benchmarks.jsonl.
    # The earlier revision_factor of .55 assumed a 97% smaller prompt meant a faster model call.
    # Measured, the opposite holds: at identical settings a revision's model call took 161.9s
    # against generation's 102.8s, because the model still reads the source TeX and reasons about
    # the edit. Estimates were consequently ~2x optimistic, which was the original complaint.
    # Every remaining sample lands within ~7% of these constants; _stage_history still overrides
    # them with measured medians per (provider, model, effort, speed) once samples accumulate.
    effort_factor=_EFFORT_FACTOR.get(effort,1)
    revision_factor=1.55 if is_revision else 1
    # ponytail: coarse name-substring buckets -- local runtimes are slower than cloud, big models slower
    # than small ones. Only the model call scales; LaTeX compile time is local and provider-independent.
    # _stage_history overrides these with measured medians per (provider, model) once samples exist.
    provider_factor={'openai':1,'anthropic':.9,'ollama':2.5,'lmstudio':2.5}.get(provider,1)
    name=(model or '').lower()
    model_factor=1.3 if 'opus' in name else .6 if any(tag in name for tag in ('haiku','mini','nano','flash')) else 1
    generation_base=105 if create_cv and create_letter else 88 if create_cv else 70
    generation=generation_base*effort_factor*revision_factor*provider_factor*model_factor/(1.9 if speed == 'fast' else 1)
    defaults={'preparing':3,'generating':generation,'generated':.5,'compiling_cv':2,'cv_compiled':.3,'compiling_letter':1.5,'letter_compiled':.3,'cached':1,'saving':3}
    plan=['preparing','generating','generated']
    if create_cv: plan += ['compiling_cv','cv_compiled']
    if create_letter: plan += ['compiling_letter','letter_compiled']
    plan += ['saving']
    key=(provider,model,effort,speed,create_cv,create_letter,is_revision)
    learned,history=_learned_timing(key)
    if learned:
        defaults.update(learned)
    else:
        # TASK-303 AC2: no run of this model at all. Measured 2026-10-16, GPT-6.1-Sol took 357 s against
        # the 83 s these constants (calibrated on GPT-5.6) gave, so an unmeasured model is padded.
        defaults['generating']*=NO_HISTORY_FACTOR
    return plan,defaults,key


# TASK-303 AC2: estimates come from cv-benchmarks.jsonl -- every finished task already appends one
# row -- grouped by route, provider, model, effort, speed and document mix, successful uncached runs
# only, median of the most recent BENCHMARK_RUNS. Read from disk, so they survive restarts.
_EFFORT_FACTOR={'low':.75,'medium':1,'high':1.3,'xhigh':1.6,'max':1.8,'ultra':2}
BENCHMARK_RUNS=10
NO_HISTORY_FACTOR=1.5
_history_cache={'stamp':None,'rows':[]}


def _benchmark_rows():
    workspace=getattr(settings,'CODEX_CV_WORKSPACE','') or ''
    path=Path(workspace)/'.dachapply-cache'/'cv-benchmarks.jsonl'
    try:
        stat=path.stat() if workspace else None
    except OSError:
        stat=None
    stamp=(str(path),stat.st_mtime_ns,stat.st_size) if stat else None
    if stamp != _history_cache['stamp']:
        rows=[]
        try:
            lines=path.read_text(encoding='utf-8').splitlines() if stat else []
        except OSError:
            lines=[]
        for line in lines:
            try:
                row=json.loads(line)
            except ValueError:
                continue
            if isinstance(row,dict) and row.get('status') == 'ready' and not row.get('cache_hit') and isinstance(row.get('stage_seconds'),dict):
                rows.append(row)
        _history_cache.update(stamp=stamp,rows=rows)
    return _history_cache['rows']


def _learned_timing(key):
    """({stage: seconds}, history) for a model task key. history is 'measured' (this exact group),
    'other_effort' (same model, route, speed and mix at other efforts, scaled by effort) or 'none' --
    never another model's runs."""
    provider,model,effort,speed,create_cv,create_letter,is_revision=key
    route='revision' if is_revision else 'generation'
    wanted=(route,provider,model,speed,bool(create_cv),bool(create_letter))
    group=[row for row in _benchmark_rows() if (row.get('route'),row.get('provider'),row.get('model'),row.get('speed'),bool(row.get('create_cv')),bool(row.get('create_letter'))) == wanted]
    exact=[row for row in group if row.get('effort') == effort]
    rows,history=(exact,'measured') if exact else (group,'other_effort') if group else ([],'none')
    stages={}
    for row in rows[-BENCHMARK_RUNS:]:
        # Only the model call scales with effort; compile and save are local work.
        scale=_EFFORT_FACTOR.get(effort,1)/_EFFORT_FACTOR.get(row.get('effort'),1) if history == 'other_effort' else 1
        for stage,seconds in row['stage_seconds'].items():
            if isinstance(seconds,(int,float)):
                stages.setdefault(stage,[]).append(seconds*scale if stage == 'generating' else seconds)
    return {stage:median(values) for stage,values in stages.items()},history


def estimate_seconds(provider, model, effort, speed, create_cv=True, create_letter=True, is_revision=False):
    """TASK-303 AC3: {'seconds', 'history'} a model picker shows for one choice of settings -- the
    same numbers a task started with them begins its countdown from."""
    plan,defaults,key=_task_timing(provider,model,effort,speed,create_cv,create_letter,is_revision)
    return {'seconds':round(sum(max(.5,defaults.get(stage,1)) for stage in plan)),'history':_learned_timing(key)[1]}


def with_expected_seconds(options):
    """TASK-303 AC3: each option plus expected_seconds[route][documents]['effort|speed'] =
    {'seconds', 'history'}, so a picker shows the duration of the exact settings chosen."""
    mixes={'both':(True,True),'cv':(True,False),'letter':(False,True)}
    return [{**option,'expected_seconds':{route:{mix:{f'{effort}|{speed}':estimate_seconds(option['provider'],option['key'],effort,speed,cv,letter,route == 'revision')
                                                      for effort in option.get('efforts',[]) for speed in (('normal','fast') if option.get('fast_tier') else ('normal',))}
                                                 for mix,(cv,letter) in mixes.items()}
                                          for route in ('generation','revision')}}
            for option in options]


def _stage_seconds(task, stage):
    samples=_stage_history.get((task['_estimate_key'],stage), [])
    return max(.5, median(samples) if samples else task['_stage_defaults'].get(stage,1))


def _record_stage(task, now):
    stage=task.get('_stage_key')
    elapsed=now-task.get('_stage_started_at',now)
    if stage in task.get('_stage_plan',()):
        task.setdefault('_stage_times',{})[stage]=round(elapsed,2)
    # TASK-303: model tasks learn from cv-benchmarks.jsonl (successful runs only); this in-memory
    # history, which also counts the stage a failed run died in, stays for compile/literal routes.
    if stage in task.get('_stage_plan',()) and elapsed >= .5 and len(task.get('_estimate_key') or ()) != 7:
        samples=_stage_history.setdefault((task['_estimate_key'],stage), [])
        samples.append(elapsed)
        del samples[:-10]


def _benchmark_row(task, now):
    key=task.get('_estimate_key') or ()
    if key and key[0] == 'compile-only':
        details={'route':'recompile'}
    elif key and key[0] == 'literal-edit':
        details={'route':'literal-edit'}
    elif len(key) == 7:
        provider,model,effort,speed,create_cv,create_letter,is_revision=key
        details={'route':'revision' if is_revision else 'generation','provider':provider,'model':model,'effort':effort,'speed':speed,'create_cv':create_cv,'create_letter':create_letter}
    else:
        details={'route':'unknown'}
    return {**details,
            'task':task.get('id',''),
            'status':task.get('status',''),
            'estimated_seconds':round(task.get('_initial_eta') or 0,2),
            'actual_seconds':round(max(0,now-task.get('_created_at',now)),2),
            'cache_hit':'cached' in (task.get('_stage_plan') or ()),
            'stage_seconds':task.get('_stage_times') or {},
            # TASK-303 AC4: a failure's own reason, so a failed run can be diagnosed after the 1 h
            # task record is gone (two GPT-6.1 revisions failed on 2026-10-15 with nothing left).
            **({'error':str(task.get('error') or '')[:300]} if task.get('status') == 'failed' else {}),
            'recorded_at':round(time.time(),3)}


def _record_benchmark(task, now):
    # Appends estimated-vs-actual duration and per-phase timings for every finished task, so ETA
    # calibration can be checked against real runs instead of guessed at.
    workspace=getattr(settings,'CODEX_CV_WORKSPACE','') or ''
    # Never create the workspace itself -- only write inside one that already exists.
    if not workspace or not Path(workspace).is_dir():
        return
    try:
        path=Path(workspace)/'.dachapply-cache'/'cv-benchmarks.jsonl'
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(_benchmark_row(task,now))+'\n')
    except Exception:
        pass  # telemetry on the critical path: a benchmark write must never take down a generation


def _remaining_runtime(task, now):
    plan=task['_stage_plan']
    stage=task.get('_stage_key')
    if stage not in plan:
        return sum(_stage_seconds(task,item) for item in plan)
    index=plan.index(stage)
    expected=_stage_seconds(task,stage)
    elapsed=max(0,now-task['_stage_started_at'])
    # Structural floor (not cosmetic): while the model call or LaTeX compile is actually running,
    # never let the estimate collapse toward "almost done" -- keep at least a few seconds of cushion.
    min_floor=2 if stage in _ACTIVE_STAGES else .5
    floor=max(min_floor,expected*.1)+max(0,elapsed-expected)*.25
    return max(expected-elapsed,floor)+sum(_stage_seconds(task,item) for item in plan[index+1:])


def _task_eta(task, now):
    if task['status'] in ('ready','failed','cancelling','cancelled'):
        return 0
    if task['status'] == 'running':
        return _remaining_runtime(task,now)
    return sum(_stage_seconds(task,item) for item in task['_stage_plan'])


def _display_progress(task, now):
    confirmed=float(task['progress'])
    if task['status'] != 'running':
        return confirmed
    stage=task.get('_stage_key')
    cap=_STAGE_CAPS.get(stage,confirmed)
    expected=_stage_seconds(task,stage)
    fraction=min(.95,max(0,now-task['_stage_started_at'])/expected)
    return round(max(confirmed,confirmed+(cap-confirmed)*fraction),1)


def _copy_to_clipboard(text):
    root=None
    try:
        import tkinter
        root=tkinter.Tk(); root.withdraw(); root.clipboard_clear(); root.clipboard_append(text); root.update()
        return True
    except Exception:
        return False
    finally:
        if root:
            root.destroy()


def copy_text_to_clipboard(text):
    """Put text on the server machine's clipboard; False when it could not (no display, no tkinter)."""
    return _copy_to_clipboard(text)


# Statuses a finished generation may promote to 'ready_to_submit'. Anything else -- applied and
# every later or closed status -- is the owner's own decision and is never overwritten.
READY_TO_SUBMIT_FROM=[status for status in JobLead.UNAPPLIED_STATUSES if status != 'ready_to_submit']


def promotable_jobs(respect_skip=True):
    """TASK-310: jobs mark_ready_to_submit may move -- unapplied, and not recommended 'skip' by their
    latest evaluation, the one the board shows (evaluations.first(), Meta ordering -created_at). A job
    without an evaluation is promoted as before. respect_skip=False is the owner's explicit final-package
    choice, which wins over the recommendation."""
    if not respect_skip:
        return JobLead.objects.filter(status__in=READY_TO_SUBMIT_FROM)
    latest=JobEvaluation.objects.filter(job=OuterRef('pk')).order_by('-created_at').values('recommendation')[:1]
    # The isnull arm is load-bearing: a negated lookup on an annotation gets no NULL handling, so
    # ~Q alone would also drop every job that has no evaluation.
    return JobLead.objects.filter(status__in=READY_TO_SUBMIT_FROM).alias(latest_recommendation=Subquery(latest)).filter(
        Q(latest_recommendation__isnull=True)|~Q(latest_recommendation='skip'))


def mark_ready_to_submit(job_id, respect_skip=True):
    """TASK-265: move an unapplied job to 'ready_to_submit' once documents exist for it.

    One conditional UPDATE, so a status the owner changed while generation ran (e.g. to applied)
    is never clobbered, and a job whose latest evaluation says 'skip' stays put (TASK-310).
    ready_to_submit is outside DATED_STATUSES, so -- as JobLeadSerializer.update does for any move
    to a non-dated status -- status_date/feedback_due_date/last_update_date are cleared. Returns the
    number of rows changed (0 or 1).

    Never raises: it runs after the documents already exist, and a failed status bump must not turn
    a finished generation into a failed task (the owner can still set the status by hand, and the
    mark_ready_to_submit command catches anything missed).
    """
    try:
        return promotable_jobs(respect_skip).filter(pk=job_id).update(
            status='ready_to_submit',status_date=None,feedback_due_date=None,last_update_date=None)
    except Exception:
        logger.exception('Could not mark job %s ready_to_submit', job_id)
        return 0


def has_prepared_drafts(job_id, user_id):
    """TASK-280.3: a job with automatically prepared variants reaches Ready to submit only when the
    owner selects its final package, so no generation, readjustment or recompile may promote it."""
    path=_artifact_metadata_path(settings.CODEX_CV_WORKSPACE,job_id,user_id)
    try:
        return bool(json.loads(path.read_text(encoding='utf-8')).get('preparation',{}).get('variants'))
    except (AttributeError,OSError,TypeError,ValueError):
        return False


def _clipboard_contents(artifacts):
    files=[Path(artifacts[key]) for key in ('cv_tex','letter_tex') if artifacts.get(key) and Path(artifacts[key]).is_file()]
    contents=[(path.name,path.read_text(encoding='utf-8')) for path in files]
    if len(contents)==1:
        return contents[0][1]
    return '\n\n'.join(f'% ===== {name} =====\n{text}' for name,text in contents)


def _clipboard_payload(artifacts, job_url):
    # TASK-250: the copied TeX gets pasted into ChatGPT, which then has the documents but not the
    # posting they were written for. A '%' line keeps the same clipboard compilable when it is pasted
    # into a .tex file instead, and needs no escaping: TeX discards a comment to end of line, so a
    # URL's %, #, &, _ or ~ are inert here -- which they would not be if the link were printed as text.
    # Kept out of _clipboard_contents so that helper stays artifacts-only for its existing callers.
    url=' '.join((job_url or '').split())  # a stray newline would close the comment and break the file
    text=_clipboard_contents(artifacts)
    return f'% Job listing: {url}\n\n{text}' if text and url else text


def _clipboard_parts(artifacts, job_url):
    # TASK-279: each document of the run on its own, with the same job-link line, so Copy TeX can
    # offer CV only or letter only. A document whose TeX is missing has no entry.
    return {kind:_clipboard_payload({f'{kind}_tex':artifacts[f'{kind}_tex']},job_url) for kind in ('cv','letter')
            if artifacts.get(f'{kind}_tex') and Path(artifacts[f'{kind}_tex']).is_file()}


def _learn_application_preference(user_id, instructions, create_cv, create_letter):
    instructions=' '.join((instructions or '').split())
    if not instructions:
        return ''
    scope='CV + letter' if create_cv and create_letter else 'CV' if create_cv else 'Letter'
    entry=f'- [{scope}] {instructions}'
    profile,_=UserProfile.objects.get_or_create(user_id=user_id)
    lines=profile.learned_application_preferences.splitlines()
    if entry.casefold() not in {line.casefold() for line in lines}:
        profile.learned_application_preferences='\n'.join([*lines,entry]).strip()
        profile.save(update_fields=['learned_application_preferences'])
    return entry


def _update(task_id, **values):
    with _lock:
        task=_tasks.get(task_id)
        if not task:
            return
        if task['status'] == 'cancelling' and values.get('status') == 'running':
            return
        now=time.monotonic()
        status=values.get('status',task['status'])
        if status == 'running' and not task.get('_started_at'):
            task['_started_at']=now
        stage=_stage_key(values.get('stage',task['stage']))
        if stage != task['_stage_key'] and status != 'failed':
            _record_stage(task,now)
            task.update(_stage_key=stage,_stage_started_at=now)
            if stage == 'cached':
                # Exact-cache route diverges from the planned generate/compile/save stages;
                # shrink the plan so step totals and ETA reflect what is actually happening.
                task['_stage_plan']=['preparing','cached']
        if status in ('ready','failed','cancelled'):
            _record_stage(task,now)
            task['_finished_at']=now
        task.update(values, updated_at=time.time())
        if status in ('ready','failed','cancelled'):
            _record_benchmark(task,now)


def _cleanup():
    cutoff=time.time()-3600
    with _lock:
        for task_id in [key for key, task in _tasks.items() if task['updated_at'] < cutoff]:
            del _tasks[task_id]


def _retry_missing_source(job):
    if job.is_meaningful_source(job.original_source_text) or not job.url:
        return
    original=job.original_source_text
    result=fetch_posting_text(job.url)
    text=result.get('text','') if result.get('ok') else ''
    if job.is_meaningful_source(text):
        JobLead.objects.filter(pk=job.pk,original_source_text=original).update(original_source_text=text)
    # A popup save can win while the network request is in flight; generation uses that newer text.
    job.refresh_from_db()


def _run(task_id, job_id, user_id, profile, cv_key, letter_key, create_letter, provider, model, effort, speed, source_cv=None, source_letter=None, revision_instructions='', create_cv=True, correction_image=None, base_templates=None, replace_existing=False, cancel_event=None, auto_clipboard=True, route_reason='', generation_options=None, mark_ready=True, on_finish=None):
    close_old_connections()
    try:
        if cancel_event.is_set():
            raise GenerationCancelled
        job=JobLead.objects.get(id=job_id)
        _retry_missing_source(job)
        if cancel_event.is_set():
            raise GenerationCancelled
        if base_templates is None and (source_cv or source_letter):
            base_templates=_latest_base_templates(job)
        generation_kwargs={'cancelled':cancel_event.is_set,'user_id':user_id}
        if base_templates:
            generation_kwargs['base_templates']=base_templates
        if replace_existing:
            generation_kwargs['replace_existing']=True
        generation_kwargs.update(generation_options or {})
        archive, filename, artifacts=generate_cv_package(job, profile, cv_key, letter_key, create_letter, provider, model, effort, speed, lambda progress, stage: _update(task_id, status='running', progress=progress, stage=stage), source_cv, source_letter, revision_instructions, create_cv, correction_image, **generation_kwargs)
        if cancel_event.is_set():
            raise GenerationCancelled
        # Generation can run for minutes with no database traffic, so the pooled connection opened
        # above is often dead by now. Recycle before the first write, or the task fails at the very
        # end with the documents already produced.
        close_old_connections()
        learned_preference=_learn_application_preference(user_id, revision_instructions, create_cv, create_letter)
        # TASK-236 AC8: the entry above is still stored verbatim -- nothing is deleted -- but
        # cv_generator.preference_exclusion decides whether it will ever be sent as a durable
        # preference again. '' means it will; anything else is the reason it will not, and the CV
        # popups render that instead of claiming the adjustment was learned for future applications.
        learned_exclusion=preference_exclusion(learned_preference)
        clipboard_tex=_clipboard_payload(artifacts,job.url)
        # TASK-261: bulk runs pass auto_clipboard=False -- N parallel tasks would each overwrite the
        # clipboard. clipboard_tex is still computed so the UI can copy it on demand.
        clipboard_copied=bool(auto_clipboard and clipboard_tex and _copy_to_clipboard(clipboard_tex))
        if 'base_templates' in artifacts:
            _record_base_templates(job,artifacts['base_templates'])
        # TASK-280.2: automatic To-apply drafts are not a chosen package, so they leave the status alone.
        if mark_ready and not has_prepared_drafts(job.id,user_id):
            mark_ready_to_submit(job.id)
        report=artifacts.get('report')
        if revision_instructions and isinstance(report,dict):
            # TASK-278 AC6: a readjustment names the route that produced it.
            report={**report,'main_changes':[*report.get('main_changes',[]),'Route: full optimization'+(f' ({route_reason})' if route_reason else '')+'.']}
        _update(task_id, status='ready', progress=100, stage='Ready', archive=archive, filename=filename, artifacts=artifacts, report=report, clipboard_tex=clipboard_tex, clipboard_tex_parts=_clipboard_parts(artifacts,job.url), clipboard_copied=clipboard_copied, learned_preference=learned_preference, learned_preference_exclusion=learned_exclusion)
    except GenerationCancelled:
        _update(task_id, status='cancelled', stage='Cancelled', error='')
    except Exception as exc:
        error=getattr(exc,'public_message',str(exc).splitlines()[0][:500])
        _update(task_id, status='failed', stage='Failed', error=error, diagnostics=getattr(exc,'diagnostics',str(exc)), repair_attempts=getattr(exc,'repair_attempts',0))
    finally:
        if on_finish:
            # TASK-280.2: persists the outcome of a prepared variant; must never mask the task's own result.
            try:
                on_finish(task_id)
            except Exception:
                logger.exception('Recording the outcome of CV task %s failed', task_id)
        close_old_connections()


def _run_compile(task_id, job_id, user_id, cv_key, source_cv, source_letter, source_updates, task_report, cancel_event, fall_back=False):
    """Compile (with source_updates: edit, then compile) the latest documents. With fall_back, a
    compile or page-limit failure -- raised before recompile_generated_package writes anything --
    is returned as a reason instead of failing the task, so the caller can run full optimization."""
    close_old_connections()
    try:
        job=JobLead.objects.get(id=job_id)
        compile_kwargs={'cancelled':cancel_event.is_set,'user_id':user_id}
        if source_updates:
            compile_kwargs['source_updates']=source_updates
        archive,filename,artifacts=recompile_generated_package(job,cv_key,source_cv,source_letter,lambda progress,stage:_update(task_id,status='running',progress=progress,stage=stage),**compile_kwargs)
        if cancel_event.is_set():
            raise GenerationCancelled
        clipboard_tex=_clipboard_payload(artifacts,job.url)
        if not has_prepared_drafts(job.id,user_id):  # TASK-280.3
            mark_ready_to_submit(job.id)
        _update(task_id,status='ready',progress=100,stage='Ready',archive=archive,filename=filename,artifacts=artifacts,report=task_report,clipboard_tex=clipboard_tex,clipboard_tex_parts=_clipboard_parts(artifacts,job.url),clipboard_copied=bool(clipboard_tex and _copy_to_clipboard(clipboard_tex)))
    except GenerationCancelled:
        _update(task_id,status='cancelled',stage='Cancelled',error='')
    except Exception as exc:
        if fall_back and isinstance(exc,RecoverableGenerationError):
            return f'the edited document failed the compile check: {str(exc).splitlines()[0][:200]}'
        _update(task_id,status='failed',stage='Failed',error=str(exc).splitlines()[0][:500],diagnostics=getattr(exc,'diagnostics',str(exc)))
    finally:
        close_old_connections()
    return ''


def _run_literal(task_id, job_id, user_id, source_cv, source_letter, instructions, pairs, local_model, fallback, cancel_event):
    """TASK-278: deterministic pairs (or the local model's translation) -> gate -> compile check ->
    write. Any refusal on the way discards every edit and runs full optimization in this same task."""
    try:
        documents=read_revision_sources([source_cv,source_letter])
        if documents is None:
            raise NotLiteral('a selected source file is missing')
        if pairs:
            route='deterministic (no AI)'
        else:
            _update(task_id,status='running',progress=5,stage=f'Reading the edit with {local_model[1]}')
            pairs=translate_literal_edits(documents,instructions,*local_model,cancel_event.is_set)
            route=f'local model ({local_model[1]})'
        updates,edits=gate_literal_edits(documents,instructions,pairs)
        reason=_run_compile(task_id,job_id,user_id,fallback['cv_key'],source_cv,source_letter,updates,literal_report(updates,edits,route),cancel_event,fall_back=True)
    except NotLiteral as exc:
        reason=str(exc)
    except GenerationCancelled:
        _update(task_id,status='cancelled',stage='Cancelled',error='')
        return
    if not reason:
        return
    plan,defaults,estimate_key=_task_timing(fallback['provider'],fallback['model'],fallback['effort'],fallback['speed'],fallback['create_cv'],fallback['create_letter'],True)
    with _lock:
        if task_id in _tasks:
            task=_tasks[task_id]
            task.update(_stage_plan=plan,_stage_defaults=defaults,_estimate_key=estimate_key,_estimate_history=_learned_timing(estimate_key)[1])
            # TASK-303: the estimate was the literal route's (the 8.5 s in the failed rows of 2026-10-15);
            # the run now ahead is a full optimization: time already spent plus that route's estimate.
            task['_initial_eta']=time.monotonic()-task['_created_at']+sum(_stage_seconds(task,stage) for stage in plan)
    _run(task_id,job_id,user_id,cancel_event=cancel_event,route_reason=reason,**fallback)


def _adopt_letter_label(job_id, user_id, letter_key, source_letter):
    """TASK-279: a letter still named '<applicant>-Letter-<target>' (before TASK-253) takes its
    template's label before a revision or compile writes it, through the TASK-271 rename path, so
    tracking and every finished task follow. Kept as is when the owner named the letter, when it is
    a sent document (those are never written), or when the new name is taken. Returns its path."""
    if not source_letter or '-Letter-' not in Path(source_letter).stem:
        return source_letter
    job=JobLead.objects.filter(id=job_id).first()
    user=get_user_model().objects.filter(pk=user_id).first()
    if not job or not user:
        return source_letter
    source=Path(source_letter)
    applicant=applicant_name(user)
    prefix=f'{applicant}-Letter-'
    label=_filename_label(_letter_label(user,letter_key))
    current=latest_generated_sources(job,user,letter_key)[1]
    # rename_generated_artifact renames the job's tracked letter, so it must be this very file.
    if (label == 'Letter' or not source.stem.startswith(prefix) or preferred_names(job,user,letter_key)[1]
            or _is_sent(source,_sent_paths(settings.CODEX_CV_WORKSPACE))
            or not current or os.path.normcase(current) != os.path.normcase(str(source))):
        return source_letter
    try:
        renamed=rename_generated_artifact(job,user,'letter',letter_key,f'{applicant}-{label}-{source.stem[len(prefix):]}',remember=False)
    except (OSError,ValueError):  # FileExistsError among them: overwrite nothing, keep the old name
        return source_letter
    rename_task_paths(user_id,renamed)
    return renamed.get(str(source),source_letter)


def no_change_requested(instructions):
    return (instructions or '').strip().partition('.')[0].strip().casefold() == 'no further cv changes required'


def start_cv_noop_task(job_id, user_id, artifacts):
    _cleanup()
    artifacts={key:path for key,path in artifacts.items() if key in ('cv_tex','cv_pdf','letter_tex','letter_pdf') and Path(path).is_file()}
    if not artifacts:
        raise ValueError('No previous generated files were found for this job.')
    archive=BytesIO()
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as bundle:
        for path in artifacts.values():
            bundle.write(path,Path(path).name)
    task_id=uuid.uuid4().hex
    now=time.monotonic()
    # TASK-250: this path has no job object -- only the id -- and the copy button is offered here too.
    job_url=JobLead.objects.filter(id=job_id).values_list('url',flat=True).first()
    clipboard_tex=_clipboard_payload(artifacts,job_url)
    with _lock:
        _tasks[task_id]={'id':task_id,'user_id':user_id,'job_id':job_id,'status':'ready','progress':100,'stage':'No changes requested','error':'','archive':archive.getvalue(),'filename':'application.zip','artifacts':artifacts,'report':{'changed_files':[],'main_changes':['Current files retained unchanged.'],'unsupported_requirements_not_claimed':[]},'clipboard_tex':clipboard_tex,'clipboard_tex_parts':_clipboard_parts(artifacts,job_url),'clipboard_copied':False,'learned_preference':'','learned_preference_exclusion':'','diagnostics':'','repair_attempts':0,'_created_at':now,'_started_at':now,'_finished_at':now,'_stage_key':'ready','_stage_started_at':now,'_stage_plan':[],'_stage_defaults':{},'_estimate_key':('no-change',),'_stage_times':{},'updated_at':time.time()}
    return task_id


def start_cv_compile_task(job_id, user_id, cv_key, source_cv=None, source_letter=None, source_updates=None, task_report=None, letter_key=''):
    _cleanup()
    renamed=_adopt_letter_label(job_id,user_id,letter_key,source_letter)
    if renamed != source_letter:
        source_updates={(renamed if key == str(source_letter) else key):value for key,value in (source_updates or {}).items()}
        if task_report and task_report.get('changed_files'):  # the report was written before the rename
            task_report={**task_report,'changed_files':[Path(renamed).name if name == Path(source_letter).name else name for name in task_report['changed_files']]}
        source_letter=renamed
    task_id=uuid.uuid4().hex
    now=time.monotonic()
    cancel_event=Event()
    compile_cv=source_cv and (not source_updates or str(source_cv) in source_updates or not Path(source_cv).with_suffix('.pdf').is_file())
    compile_letter=source_letter and (not source_updates or str(source_letter) in source_updates or not Path(source_letter).with_suffix('.pdf').is_file())
    plan=(['compiling_cv','cv_compiled'] if compile_cv else [])+(['compiling_letter','letter_compiled'] if compile_letter else [])
    with _lock:
        _tasks[task_id]={'id':task_id,'user_id':user_id,'job_id':job_id,'status':'queued','progress':0,'stage':'Queued','error':'','archive':None,'filename':'','artifacts':{},'report':task_report,'clipboard_tex':'','clipboard_tex_parts':{},'clipboard_copied':False,'learned_preference':'','learned_preference_exclusion':'','diagnostics':'','repair_attempts':0,'_cancel':cancel_event,'_created_at':now,'_started_at':None,'_finished_at':None,'_stage_key':'queued','_stage_started_at':now,'_stage_plan':plan,'_stage_defaults':{'compiling_cv':2,'cv_compiled':.3,'compiling_letter':1.5,'letter_compiled':.3},'_estimate_key':('compile-only',bool(compile_cv),bool(compile_letter)),'_stage_times':{},'updated_at':time.time()}
        _tasks[task_id]['_initial_eta']=sum(_stage_seconds(_tasks[task_id],stage) for stage in _tasks[task_id]['_stage_plan'])
    Thread(target=_run_compile,args=(task_id,job_id,user_id,cv_key,source_cv,source_letter,source_updates or {},task_report,cancel_event),name=f'cv-compile-{task_id[:8]}',daemon=True).start()
    return task_id


def start_cv_literal_task(job_id, user_id, source_cv, source_letter, instructions, pairs, local_model, fallback):
    """TASK-278: a literal readjustment from deterministic `pairs` or, when pairs is None, from
    `local_model`'s translation. `fallback` holds _run's keyword arguments (profile, cv_key, ...,
    revision_instructions) for the full-optimization run that any refusal turns into."""
    _cleanup()
    if source_letter:
        source_letter=fallback['source_letter']=_adopt_letter_label(job_id,user_id,fallback['letter_key'],source_letter)
    task_id=uuid.uuid4().hex
    now=time.monotonic()
    cancel_event=Event()
    plan=([] if pairs else ['working'])+(['compiling_cv','cv_compiled'] if source_cv else [])+(['compiling_letter','letter_compiled'] if source_letter else [])
    config={key:fallback[key] for key in ('profile','cv_key','letter_key','create_letter','create_cv','provider','model','effort','speed')}
    with _lock:
        _tasks[task_id]={'id':task_id,'user_id':user_id,'job_id':job_id,'status':'queued','progress':0,'stage':'Queued','error':'','archive':None,'filename':'','artifacts':{},'report':None,'clipboard_tex':'','clipboard_tex_parts':{},'clipboard_copied':False,'learned_preference':'','learned_preference_exclusion':'','diagnostics':'','repair_attempts':0,'_config':config,'_cancel':cancel_event,'_created_at':now,'_started_at':None,'_finished_at':None,'_stage_key':'queued','_stage_started_at':now,'_stage_plan':plan,'_stage_defaults':{'working':6,'compiling_cv':2,'cv_compiled':.3,'compiling_letter':1.5,'letter_compiled':.3},'_estimate_key':('literal-edit',bool(pairs),bool(source_cv),bool(source_letter)),'_stage_times':{},'updated_at':time.time()}
        _tasks[task_id]['_initial_eta']=sum(_stage_seconds(_tasks[task_id],stage) for stage in plan)
    Thread(target=_run_literal,args=(task_id,job_id,user_id,source_cv,source_letter,instructions,pairs,local_model,fallback,cancel_event),name=f'cv-literal-{task_id[:8]}',daemon=True).start()
    return task_id


def start_cv_task(job_id, user_id, profile, cv_key, letter_key, create_letter, provider, model, effort, speed, source_cv=None, source_letter=None, revision_instructions='', create_cv=True, correction_image=None, base_templates=None, replace_existing=False, auto_clipboard=True, generation_options=None, mark_ready=True, on_finish=None):
    _cleanup()
    if create_letter:
        source_letter=_adopt_letter_label(job_id,user_id,letter_key,source_letter)
    task_id=uuid.uuid4().hex
    now=time.monotonic()
    plan,defaults,estimate_key=_task_timing(provider,model,effort,speed,create_cv,create_letter,bool(source_cv or source_letter or revision_instructions or correction_image))
    cancel_event=Event()
    with _lock:
        _tasks[task_id]={'id':task_id,'user_id':user_id,'job_id':job_id,'status':'queued','progress':0,'stage':'Queued','error':'','archive':None,'filename':'','artifacts':{},'report':None,'clipboard_tex':'','clipboard_tex_parts':{},'clipboard_copied':False,'learned_preference':'','learned_preference_exclusion':'','diagnostics':'','repair_attempts':0,'_config':{'profile':profile,'cv_key':cv_key,'letter_key':letter_key,'create_letter':create_letter,'create_cv':create_cv,'provider':provider,'model':model,'effort':effort,'speed':speed,'generation_options':generation_options},'_cancel':cancel_event,'_created_at':now,'_started_at':None,'_finished_at':None,'_stage_key':'queued','_stage_started_at':now,'_stage_plan':plan,'_stage_defaults':defaults,'_estimate_key':estimate_key,'_stage_times':{},'updated_at':time.time()}
        _tasks[task_id]['_initial_eta']=sum(_stage_seconds(_tasks[task_id],stage) for stage in plan)
        _tasks[task_id]['_estimate_history']=_learned_timing(estimate_key)[1]
    # ponytail: one local CLI agent per task; add a concurrency cap if large batches exhaust the workstation.
    Thread(target=_run, args=(task_id,job_id,user_id,profile,cv_key,letter_key,create_letter,provider,model,effort,speed,source_cv,source_letter,revision_instructions,create_cv,correction_image,base_templates,replace_existing,cancel_event,auto_clipboard,'',generation_options,mark_ready,on_finish), name=f'cv-agent-{task_id[:8]}', daemon=True).start()
    return task_id


def get_cv_task(task_id, user_id):
    _cleanup()
    with _lock:
        task=_tasks.get(task_id)
        if not task or task['user_id'] != user_id:
            return None
        now=time.monotonic()
        end=task.get('_finished_at') or now
        public={key:value for key,value in task.items() if key not in ('archive','user_id','updated_at') and not key.startswith('_')}
        step_completed,step_total,step_label=_step_progress(task)
        public.update(progress=_display_progress(task,now),elapsed_seconds=math.ceil(max(0,end-task['_created_at'])),estimated_seconds_remaining=math.ceil(_task_eta(task,now)),step_label=step_label,step_completed=step_completed,step_total=step_total)
        if task.get('_estimate_history'):
            public['estimate_history']=task['_estimate_history']  # TASK-303 AC2: 'none' = no timing for this model yet
        return public


def cancel_cv_task(task_id, user_id):
    _cleanup()
    with _lock:
        task=_tasks.get(task_id)
        if not task or task['user_id'] != user_id:
            return None
        if task['status'] in ('ready','failed','cancelled'):
            return False
        task['_cancel'].set()
        task.update(status='cancelling', stage='Cancelling', _stage_key='cancelling', _stage_started_at=time.monotonic(), updated_at=time.time())
        return True


def start_cv_revision(task_id, user_id, instructions, correction_image=None):
    instructions=(instructions or '').strip()
    if not instructions and not correction_image:
        raise ValueError('Provide revision instructions or a correction image.')
    with _lock:
        parent=_tasks.get(task_id)
        if not parent or parent['user_id'] != user_id or parent['status'] != 'ready' or '_config' not in parent:
            raise ValueError('Completed generation task not found.')
        config=dict(parent['_config'])
        artifacts=dict(parent['artifacts'])
        job_id=parent['job_id']
    if no_change_requested(instructions) and not correction_image:
        return task_id
    kwargs={'source_cv':artifacts.get('cv_tex'),'source_letter':artifacts.get('letter_tex'),'revision_instructions':instructions[:5000],'correction_image':correction_image}
    if artifacts.get('base_templates'):
        kwargs['base_templates']=artifacts['base_templates']
    return start_cv_task(job_id, user_id, **config, **kwargs)


def rename_task_paths(user_id, renamed):
    """TASK-271: finished tasks follow a rename of their files -- artifact paths (so Readjust and
    Reveal keep working), the download zip's entry names and the Copy TeX text."""
    names={Path(old).name:Path(new).name for old,new in renamed.items()}
    with _lock:
        tasks=[task for task in _tasks.values() if task['user_id'] == user_id and set(renamed)&{value for value in (task.get('artifacts') or {}).values() if isinstance(value,str)}]
        for task in tasks:
            task['artifacts']={key:renamed.get(value,value) if isinstance(value,str) else value for key,value in task['artifacts'].items()}
            if task.get('archive'):
                source=zipfile.ZipFile(BytesIO(task['archive']))
                archive=BytesIO()
                with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as bundle:
                    for info in source.infolist():
                        bundle.writestr(names.get(info.filename,info.filename),source.read(info))
                task['archive']=archive.getvalue()
    for task in tasks:
        if task.get('clipboard_tex'):
            job_url=JobLead.objects.filter(id=task['job_id']).values_list('url',flat=True).first()
            task['clipboard_tex']=_clipboard_payload(task['artifacts'],job_url)
            task['clipboard_tex_parts']=_clipboard_parts(task['artifacts'],job_url)


def get_cv_task_download(task_id, user_id):
    with _lock:
        task=_tasks.get(task_id)
        if not task or task['user_id'] != user_id or task['status'] != 'ready':
            return None
        return task['archive'], task['filename']
