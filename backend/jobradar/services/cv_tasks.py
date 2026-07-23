import time
import uuid
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

from django.db import close_old_connections

from jobradar.models import JobLead
from jobradar.services.cv_generator import generate_cv_package


_executor=ThreadPoolExecutor(max_workers=1, thread_name_prefix='cv-generation')
_tasks={}
_lock=Lock()


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


def _update(task_id, **values):
    with _lock:
        if task_id in _tasks:
            _tasks[task_id].update(values, updated_at=time.time())


def _cleanup():
    cutoff=time.time()-3600
    with _lock:
        for task_id in [key for key, task in _tasks.items() if task['updated_at'] < cutoff]:
            del _tasks[task_id]


def _run(task_id, job_id, profile, cv_key, letter_key, create_letter, provider, model, effort, speed, source_cv=None, source_letter=None, revision_instructions='', create_cv=True):
    close_old_connections()
    try:
        job=JobLead.objects.get(id=job_id)
        archive, filename, artifacts=generate_cv_package(job, profile, cv_key, letter_key, create_letter, provider, model, effort, speed, lambda progress, stage: _update(task_id, status='running', progress=progress, stage=stage), source_cv, source_letter, revision_instructions, create_cv)
        tex_path=artifacts.get('cv_tex') or artifacts.get('letter_tex')
        clipboard_tex=Path(tex_path).read_text(encoding='utf-8') if tex_path and Path(tex_path).is_file() else ''
        clipboard_copied=bool(clipboard_tex and _copy_to_clipboard(clipboard_tex))
        _update(task_id, status='ready', progress=100, stage='Ready', archive=archive, filename=filename, artifacts=artifacts, report=artifacts.get('report'), clipboard_tex=clipboard_tex, clipboard_copied=clipboard_copied)
    except Exception as exc:
        _update(task_id, status='failed', stage=str(exc), error=str(exc))
    finally:
        close_old_connections()


def start_cv_task(job_id, user_id, profile, cv_key, letter_key, create_letter, provider, model, effort, speed, source_cv=None, source_letter=None, revision_instructions='', create_cv=True):
    _cleanup()
    task_id=uuid.uuid4().hex
    with _lock:
        _tasks[task_id]={'id':task_id,'user_id':user_id,'job_id':job_id,'status':'queued','progress':0,'stage':'Queued','error':'','archive':None,'filename':'','artifacts':{},'report':None,'clipboard_tex':'','clipboard_copied':False,'_config':{'profile':profile,'cv_key':cv_key,'letter_key':letter_key,'create_letter':create_letter,'create_cv':create_cv,'provider':provider,'model':model,'effort':effort,'speed':speed},'updated_at':time.time()}
    _executor.submit(_run, task_id, job_id, profile, cv_key, letter_key, create_letter, provider, model, effort, speed, source_cv, source_letter, revision_instructions, create_cv)
    return task_id


def get_cv_task(task_id, user_id):
    _cleanup()
    with _lock:
        task=_tasks.get(task_id)
        if not task or task['user_id'] != user_id:
            return None
        return {key:value for key,value in task.items() if key not in ('archive','user_id','updated_at','_config')}


def start_cv_revision(task_id, user_id, instructions):
    instructions=(instructions or '').strip()
    if not instructions:
        raise ValueError('Provide revision instructions.')
    with _lock:
        parent=_tasks.get(task_id)
        if not parent or parent['user_id'] != user_id or parent['status'] != 'ready':
            raise ValueError('Completed generation task not found.')
        config=dict(parent['_config'])
        artifacts=dict(parent['artifacts'])
        job_id=parent['job_id']
    return start_cv_task(job_id, user_id, **config, source_cv=artifacts.get('cv_tex'), source_letter=artifacts.get('letter_tex'), revision_instructions=instructions[:5000])


def get_cv_task_download(task_id, user_id):
    with _lock:
        task=_tasks.get(task_id)
        if not task or task['user_id'] != user_id or task['status'] != 'ready':
            return None
        return task['archive'], task['filename']
