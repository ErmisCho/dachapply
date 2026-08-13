import math
import time
import uuid
from pathlib import Path
from statistics import median
from threading import Event, Lock, Thread

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
    if value == 'saving files': return 'saving'
    if value in ('cancelling','cancelled'): return value
    if value == 'ready': return 'ready'
    return 'working'


def _task_timing(provider, model, effort, speed, create_cv, create_letter, is_revision):
    effort_factor={'low':.75,'medium':1,'high':1.3,'xhigh':1.6,'max':1.8,'ultra':2}.get(effort,1)
    generation=(180 if create_cv and create_letter else 150 if create_cv else 120)*effort_factor/(1.5 if speed == 'fast' else 1)
    defaults={'preparing':3,'generating':generation,'generated':1,'compiling_cv':15,'cv_compiled':1,'compiling_letter':10,'letter_compiled':1,'saving':4}
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
    if stage in task.get('_stage_plan',()) and elapsed >= .5:
        samples=_stage_history.setdefault((task['_estimate_key'],stage), [])
        samples.append(elapsed)
        del samples[:-10]


def _remaining_runtime(task, now):
    plan=task['_stage_plan']
    stage=task.get('_stage_key')
    if stage not in plan:
        return sum(_stage_seconds(task,item) for item in plan)
    index=plan.index(stage)
    expected=_stage_seconds(task,stage)
    elapsed=max(0,now-task['_stage_started_at'])
    floor=max(1,expected*.1)+max(0,elapsed-expected)*.25
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
        if status in ('ready','failed','cancelled'):
            task['_finished_at']=now
        task.update(values, updated_at=time.time())


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
        archive, filename, artifacts=generate_cv_package(job, profile, cv_key, letter_key, create_letter, provider, model, effort, speed, lambda progress, stage: _update(task_id, status='running', progress=progress, stage=stage), source_cv, source_letter, revision_instructions, create_cv, correction_image, cancelled=cancel_event.is_set)
        if cancel_event.is_set():
            raise GenerationCancelled
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
        archive,filename,artifacts=recompile_generated_package(job,cv_key,source_cv,source_letter,lambda progress,stage:_update(task_id,status='running',progress=progress,stage=stage),cancelled=cancel_event.is_set)
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
        _tasks[task_id]={'id':task_id,'user_id':user_id,'job_id':job_id,'status':'queued','progress':0,'stage':'Queued','error':'','archive':None,'filename':'','artifacts':{},'report':None,'clipboard_tex':'','clipboard_copied':False,'learned_preference':'','diagnostics':'','repair_attempts':0,'_cancel':cancel_event,'_created_at':now,'_started_at':None,'_finished_at':None,'_stage_key':'queued','_stage_started_at':now,'_stage_plan':plan,'_stage_defaults':{'compiling_cv':8,'cv_compiled':1,'compiling_letter':6,'letter_compiled':1},'_estimate_key':('compile-only',bool(source_cv),bool(source_letter)),'updated_at':time.time()}
    Thread(target=_run_compile,args=(task_id,job_id,user_id,cv_key,source_cv,source_letter,cancel_event),name=f'cv-compile-{task_id[:8]}',daemon=True).start()
    return task_id


def start_cv_task(job_id, user_id, profile, cv_key, letter_key, create_letter, provider, model, effort, speed, source_cv=None, source_letter=None, revision_instructions='', create_cv=True, correction_image=None):
    _cleanup()
    task_id=uuid.uuid4().hex
    now=time.monotonic()
    plan,defaults,estimate_key=_task_timing(provider,model,effort,speed,create_cv,create_letter,bool(source_cv or source_letter or revision_instructions or correction_image))
    cancel_event=Event()
    with _lock:
        _tasks[task_id]={'id':task_id,'user_id':user_id,'job_id':job_id,'status':'queued','progress':0,'stage':'Queued','error':'','archive':None,'filename':'','artifacts':{},'report':None,'clipboard_tex':'','clipboard_copied':False,'learned_preference':'','diagnostics':'','repair_attempts':0,'_config':{'profile':profile,'cv_key':cv_key,'letter_key':letter_key,'create_letter':create_letter,'create_cv':create_cv,'provider':provider,'model':model,'effort':effort,'speed':speed},'_cancel':cancel_event,'_created_at':now,'_started_at':None,'_finished_at':None,'_stage_key':'queued','_stage_started_at':now,'_stage_plan':plan,'_stage_defaults':defaults,'_estimate_key':estimate_key,'updated_at':time.time()}
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
        public.update(progress=_display_progress(task,now),elapsed_seconds=math.ceil(max(0,end-task['_created_at'])),estimated_seconds_remaining=math.ceil(_task_eta(task,now)))
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
