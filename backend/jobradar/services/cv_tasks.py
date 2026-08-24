import json
import math
import time
import uuid
from pathlib import Path
from statistics import median
from threading import Event, Lock, Thread

from django.conf import settings
from django.db import close_old_connections

from jobradar.models import JobLead, UserProfile
from jobradar.services.cv_generator import GenerationCancelled, generate_cv_package, recompile_generated_package


_tasks={}
_stage_history={}
_lock=Lock()

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
    effort_factor={'low':.75,'medium':1,'high':1.3,'xhigh':1.6,'max':1.8,'ultra':2}.get(effort,1)
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
    # ponytail: first run uses conservative timings; persist samples only if estimates must survive server restarts.
    return plan,defaults,(provider,model,effort,speed,create_cv,create_letter,is_revision)


def _stage_seconds(task, stage):
    samples=_stage_history.get((task['_estimate_key'],stage), [])
    return max(.5, median(samples) if samples else task['_stage_defaults'].get(stage,1))


def _record_stage(task, now):
    stage=task.get('_stage_key')
    elapsed=now-task.get('_stage_started_at',now)
    if stage in task.get('_stage_plan',()):
        task.setdefault('_stage_times',{})[stage]=round(elapsed,2)
    if stage in task.get('_stage_plan',()) and elapsed >= .5:
        samples=_stage_history.setdefault((task['_estimate_key'],stage), [])
        samples.append(elapsed)
        del samples[:-10]


def _benchmark_row(task, now):
    key=task.get('_estimate_key') or ()
    if key and key[0] == 'compile-only':
        details={'route':'recompile'}
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


def _clipboard_contents(artifacts):
    files=[Path(artifacts[key]) for key in ('cv_tex','letter_tex') if artifacts.get(key) and Path(artifacts[key]).is_file()]
    contents=[(path.name,path.read_text(encoding='utf-8')) for path in files]
    if len(contents)==1:
        return contents[0][1]
    return '\n\n'.join(f'% ===== {name} =====\n{text}' for name,text in contents)


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


def _run(task_id, job_id, user_id, profile, cv_key, letter_key, create_letter, provider, model, effort, speed, source_cv=None, source_letter=None, revision_instructions='', create_cv=True, correction_image=None, cancel_event=None):
    close_old_connections()
    try:
        if cancel_event.is_set():
            raise GenerationCancelled
        job=JobLead.objects.get(id=job_id)
        archive, filename, artifacts=generate_cv_package(job, profile, cv_key, letter_key, create_letter, provider, model, effort, speed, lambda progress, stage: _update(task_id, status='running', progress=progress, stage=stage), source_cv, source_letter, revision_instructions, create_cv, correction_image, cancelled=cancel_event.is_set, user_id=user_id)
        if cancel_event.is_set():
            raise GenerationCancelled
        # Generation can run for minutes with no database traffic, so the pooled connection opened
        # above is often dead by now. Recycle before the first write, or the task fails at the very
        # end with the documents already produced.
        close_old_connections()
        learned_preference=_learn_application_preference(user_id, revision_instructions, create_cv, create_letter)
        clipboard_tex=_clipboard_contents(artifacts)
        clipboard_copied=bool(clipboard_tex and _copy_to_clipboard(clipboard_tex))
        _update(task_id, status='ready', progress=100, stage='Ready', archive=archive, filename=filename, artifacts=artifacts, report=artifacts.get('report'), clipboard_tex=clipboard_tex, clipboard_copied=clipboard_copied, learned_preference=learned_preference)
    except GenerationCancelled:
        _update(task_id, status='cancelled', stage='Cancelled', error='')
    except Exception as exc:
        error=getattr(exc,'public_message',str(exc).splitlines()[0][:500])
        _update(task_id, status='failed', stage='Failed', error=error, diagnostics=getattr(exc,'diagnostics',str(exc)), repair_attempts=getattr(exc,'repair_attempts',0))
    finally:
        close_old_connections()


def _run_compile(task_id, job_id, user_id, cv_key, source_cv, source_letter, cancel_event):
    close_old_connections()
    try:
        job=JobLead.objects.get(id=job_id)
        archive,filename,artifacts=recompile_generated_package(job,cv_key,source_cv,source_letter,lambda progress,stage:_update(task_id,status='running',progress=progress,stage=stage),cancelled=cancel_event.is_set,user_id=user_id)
        if cancel_event.is_set():
            raise GenerationCancelled
        clipboard_tex=_clipboard_contents(artifacts)
        _update(task_id,status='ready',progress=100,stage='Ready',archive=archive,filename=filename,artifacts=artifacts,clipboard_tex=clipboard_tex,clipboard_copied=bool(clipboard_tex and _copy_to_clipboard(clipboard_tex)))
    except GenerationCancelled:
        _update(task_id,status='cancelled',stage='Cancelled',error='')
    except Exception as exc:
        _update(task_id,status='failed',stage='Failed',error=str(exc).splitlines()[0][:500],diagnostics=getattr(exc,'diagnostics',str(exc)))
    finally:
        close_old_connections()


def start_cv_compile_task(job_id, user_id, cv_key, source_cv=None, source_letter=None):
    _cleanup()
    task_id=uuid.uuid4().hex
    now=time.monotonic()
    cancel_event=Event()
    plan=(['compiling_cv','cv_compiled'] if source_cv else [])+(['compiling_letter','letter_compiled'] if source_letter else [])
    with _lock:
        _tasks[task_id]={'id':task_id,'user_id':user_id,'job_id':job_id,'status':'queued','progress':0,'stage':'Queued','error':'','archive':None,'filename':'','artifacts':{},'report':None,'clipboard_tex':'','clipboard_copied':False,'learned_preference':'','diagnostics':'','repair_attempts':0,'_cancel':cancel_event,'_created_at':now,'_started_at':None,'_finished_at':None,'_stage_key':'queued','_stage_started_at':now,'_stage_plan':plan,'_stage_defaults':{'compiling_cv':2,'cv_compiled':.3,'compiling_letter':1.5,'letter_compiled':.3},'_estimate_key':('compile-only',bool(source_cv),bool(source_letter)),'_stage_times':{},'updated_at':time.time()}
        _tasks[task_id]['_initial_eta']=sum(_stage_seconds(_tasks[task_id],stage) for stage in _tasks[task_id]['_stage_plan'])
    Thread(target=_run_compile,args=(task_id,job_id,user_id,cv_key,source_cv,source_letter,cancel_event),name=f'cv-compile-{task_id[:8]}',daemon=True).start()
    return task_id


def start_cv_task(job_id, user_id, profile, cv_key, letter_key, create_letter, provider, model, effort, speed, source_cv=None, source_letter=None, revision_instructions='', create_cv=True, correction_image=None):
    _cleanup()
    task_id=uuid.uuid4().hex
    now=time.monotonic()
    plan,defaults,estimate_key=_task_timing(provider,model,effort,speed,create_cv,create_letter,bool(source_cv or source_letter or revision_instructions or correction_image))
    cancel_event=Event()
    with _lock:
        _tasks[task_id]={'id':task_id,'user_id':user_id,'job_id':job_id,'status':'queued','progress':0,'stage':'Queued','error':'','archive':None,'filename':'','artifacts':{},'report':None,'clipboard_tex':'','clipboard_copied':False,'learned_preference':'','diagnostics':'','repair_attempts':0,'_config':{'profile':profile,'cv_key':cv_key,'letter_key':letter_key,'create_letter':create_letter,'create_cv':create_cv,'provider':provider,'model':model,'effort':effort,'speed':speed},'_cancel':cancel_event,'_created_at':now,'_started_at':None,'_finished_at':None,'_stage_key':'queued','_stage_started_at':now,'_stage_plan':plan,'_stage_defaults':defaults,'_estimate_key':estimate_key,'_stage_times':{},'updated_at':time.time()}
        _tasks[task_id]['_initial_eta']=sum(_stage_seconds(_tasks[task_id],stage) for stage in plan)
    # ponytail: one local CLI agent per task; add a concurrency cap if large batches exhaust the workstation.
    Thread(target=_run, args=(task_id, job_id, user_id, profile, cv_key, letter_key, create_letter, provider, model, effort, speed, source_cv, source_letter, revision_instructions, create_cv, correction_image, cancel_event), name=f'cv-agent-{task_id[:8]}', daemon=True).start()
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
    return start_cv_task(job_id, user_id, **config, source_cv=artifacts.get('cv_tex'), source_letter=artifacts.get('letter_tex'), revision_instructions=instructions[:5000], correction_image=correction_image)


def get_cv_task_download(task_id, user_id):
    with _lock:
        task=_tasks.get(task_id)
        if not task or task['user_id'] != user_id or task['status'] != 'ready':
            return None
        return task['archive'], task['filename']
