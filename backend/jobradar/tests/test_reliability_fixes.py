from threading import Event

import pytest
from django.db import OperationalError

from jobradar.services import cv_generator, cv_tasks
from jobradar.tests.test_api import job, owner  # noqa: F401 -- fixtures


def test_task_395_dropped_connection_on_save_retries_without_rerunning_the_model(db, job, owner, monkeypatch):
    models=[]; saves=[]; closed=[]
    monkeypatch.setattr(cv_tasks,'generate_cv_package',lambda *a,**k:(models.append(1),(b'zip','a.zip',{}))[1])

    def flaky(*a,**k):
        saves.append(1)
        if len(saves)==1:
            raise OperationalError('server closed the connection unexpectedly')
        return ''
    monkeypatch.setattr(cv_tasks,'_learn_application_preference',flaky)
    monkeypatch.setattr(cv_tasks,'connections',type('C',(),{'close_all':staticmethod(lambda:closed.append(1))}))  # a real close would drop the test's sqlite :memory: db
    monkeypatch.setattr(cv_tasks,'_clipboard_contents',lambda artifacts:'')
    monkeypatch.setattr(cv_tasks,'_copy_to_clipboard',lambda text:False)
    cv_tasks._tasks['t395']={'id':'t395','user_id':owner.id,'job_id':job.id,'status':'running','stage':'x','_stage_key':'x','_stage_started_at':0,'_stage_plan':[],'_stage_times':{},'_created_at':0,'_started_at':0,'progress':0,'updated_at':0}
    try:
        cv_tasks._run('t395',job.id,owner.id,'ctx','en','',False,'openai','gpt-5.5','medium','normal',revision_instructions='tweak',cancel_event=Event())
        assert cv_tasks._tasks['t395']['status']=='ready'
    finally:
        cv_tasks._tasks.pop('t395',None)
    assert len(models)==1 and len(saves)==2 and closed==[1]


def test_task_396_unicode_comparison_symbols_are_mapped_for_pdflatex(tmp_path, monkeypatch):
    monkeypatch.setattr(cv_generator.shutil,'which',lambda name:'pdflatex')
    seen=[]
    def fake_run(command,cancelled=None,**kwargs):
        seen.append((tmp_path/'cv.tex').read_text(encoding='utf-8'))
        raise StopIteration  # the source was captured; skip the page-count check
    monkeypatch.setattr(cv_generator,'_run_command',fake_run)
    (tmp_path/'cv.tex').write_text('latency ≤ 5 ms, a → b, ≥ 3','utf-8')
    with pytest.raises(StopIteration):
        cv_generator._compile_pdf(tmp_path,'cv.tex',True)
    assert '≤' not in seen[0] and r'\ensuremath{\leq}' in seen[0] and r'\ensuremath{\geq}' in seen[0] and r'\ensuremath{\rightarrow}' in seen[0]

    plain='Größe – Straße é'.encode('utf-8')
    (tmp_path/'cv.tex').write_bytes(plain)
    with pytest.raises(StopIteration):
        cv_generator._compile_pdf(tmp_path,'cv.tex',True)
    assert (tmp_path/'cv.tex').read_bytes()==plain


def test_task_397_locked_file_is_retried_then_replaced(tmp_path, monkeypatch):
    monkeypatch.setattr(cv_generator.time,'sleep',lambda s:None)
    src=tmp_path/'a.tmp'; dst=tmp_path/'a.json'; src.write_text('x')
    real=type(src).replace; calls=[]
    def locked_twice(self,target):
        calls.append(1)
        if len(calls)<3:
            raise PermissionError(32,'The process cannot access the file (WinError 32)')
        return real(self,target)
    monkeypatch.setattr(type(src),'replace',locked_twice)
    cv_generator._retry_locked(src.replace,dst)
    assert dst.read_text()=='x' and len(calls)==3


def test_task_397_persistent_lock_still_raises(monkeypatch, tmp_path):
    monkeypatch.setattr(cv_generator.time,'sleep',lambda s:None)
    def always(*a):
        raise PermissionError(32,'in use')
    with pytest.raises(PermissionError):
        cv_generator._retry_locked(always,tmp_path)
