import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

from django.db import close_old_connections

from jobradar.models import JobLead
from jobradar.services.cv_generator import generate_cv_package


_executor=ThreadPoolExecutor(max_workers=1, thread_name_prefix='cv-generation')
_tasks={}
_lock=Lock()


def _update(task_id, **values):
    with _lock:
        if task_id in _tasks:
            _tasks[task_id].update(values, updated_at=time.time())


def _cleanup():
    cutoff=time.time()-3600
    with _lock:
        for task_id in [key for key, task in _tasks.items() if task['updated_at'] < cutoff]:
            del _tasks[task_id]


def _run(task_id, job_id, profile, cv_key, letter_key, provider, model, effort, speed):
    close_old_connections()
    try:
        job=JobLead.objects.get(id=job_id)
        archive, filename=generate_cv_package(job, profile, cv_key, letter_key, provider, model, effort, speed, lambda progress, stage: _update(task_id, status='running', progress=progress, stage=stage))
        _update(task_id, status='ready', progress=100, stage='Ready', archive=archive, filename=filename)
    except Exception as exc:
        _update(task_id, status='failed', stage=str(exc), error=str(exc))
    finally:
        close_old_connections()


def start_cv_task(job_id, user_id, profile, cv_key, letter_key, provider, model, effort, speed):
    _cleanup()
    task_id=uuid.uuid4().hex
    with _lock:
        _tasks[task_id]={'id':task_id,'user_id':user_id,'job_id':job_id,'status':'queued','progress':0,'stage':'Queued','error':'','archive':None,'filename':'','updated_at':time.time()}
    _executor.submit(_run, task_id, job_id, profile, cv_key, letter_key, provider, model, effort, speed)
    return task_id


def get_cv_task(task_id, user_id):
    _cleanup()
    with _lock:
        task=_tasks.get(task_id)
        if not task or task['user_id'] != user_id:
            return None
        return {key:value for key,value in task.items() if key not in ('archive','user_id','updated_at')}


def get_cv_task_download(task_id, user_id):
    with _lock:
        task=_tasks.get(task_id)
        if not task or task['user_id'] != user_id or task['status'] != 'ready':
            return None
        return task['archive'], task['filename']
