"""TASK-366: private subprocess fixture, never imported by the application."""
import json
import atexit
import os
from pathlib import Path
import sys
import threading
import time
from datetime import timedelta

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'backend'))
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings_test'
os.environ['DACHAPPLY_CONTROL_DB'] = ''  # TASK-366: never attach fixture work to an owner's durable supervisor.
from config import settings_test

root = Path(sys.argv[1])
unused_workspace = settings_test.CODEX_CV_WORKSPACE
atexit.register(lambda: Path(unused_workspace).rmdir())  # TASK-366: also clean up when migrations/startup fail.
settings_test.DATABASES['default']['NAME'] = str(root / 'data.sqlite3')
settings_test.CODEX_CV_WORKSPACE = str(root / 'workspace')
(root / 'workspace').mkdir()
settings_test.CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}
settings_test.CSRF_TRUSTED_ORIGINS = [sys.argv[3]]
settings_test.CODEX_CV_ENABLED = True
settings_test.CODEX_CV_OPEN_OUTPUT_FOLDER = False
settings_test.CODEX_CV_CACHE = False
settings_test.CODEX_CANDIDATE_EVIDENCE_PATH = ''  # TASK-366: never fall back to owner evidence.
settings_test.CODEX_APPLICATION_RULES_PATH = str(root / 'rules.md')
(root / 'rules.md').write_text('Use only the synthetic fixture evidence.', encoding='utf-8')
settings_test.ALLOWED_HOSTS = ['127.0.0.1', 'localhost']

import django
django.setup()
from django.core.management import call_command
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.servers.basehttp import ThreadedWSGIServer, WSGIRequestHandler
from django.core.wsgi import get_wsgi_application
from jobradar.models import CvAsset, JobLead, UserProfile
from jobradar.services import application_prep as prep, cv_generator as generator, cv_tasks, job_evaluator
from jobradar.tests.test_application_prep import POSTING

# TASK-366: deny external sockets and subprocesses even if a fixture misses a provider boundary.
def audit(event, args):
    if event == 'subprocess.Popen':
        raise RuntimeError('TASK-366 forbids subprocesses')
    if event == 'socket.connect' and args[1][0] not in ('127.0.0.1', '::1'):
        raise RuntimeError('TASK-366 forbids external connections')
sys.addaudithook(audit)
call_command('migrate', verbosity=0)
call_command('createcachetable', verbosity=0)
user = User.objects.create_user('recovery-test', password='fixture-password')
UserProfile.objects.update_or_create(user=user, defaults={'can_generate_cv': True, 'candidate_profile': 'Synthetic engineer', 'candidate_evidence': 'Synthetic Python experience.'})
CvAsset.objects.create(user=user, kind=CvAsset.KIND_CV, key='en', language='en', label='Fixture CV', filename='fixture.tex', source='Synthetic CV')
jobs = [JobLead.objects.create(created_by=user, company=name, title='Engineer', original_source_text=POSTING, url='https://example.invalid/jobs/cloud' if name[0]=='C' else '') for name in ('Cloud fixture', 'Limit fixture')]
options = [{'provider': 'openai', 'key': 'gpt-5.5', 'label': 'Fixture cloud', 'efforts': ['medium'], 'default_effort': 'medium', 'tools': True, 'fast_tier': False}]
release = threading.Event()
stopping = threading.Event()  # TASK-366: discovery release must not cancel generation.
calls = []

def discover():
    assert release.wait(60), 'Discovery fixture was not released'
    return options
generator._discover_model_options = discover
generator.cloud_model_options = lambda: options
prep.cloud_model_options = generator.cloud_model_options
prep.fetch_missing_sources = lambda jobs: None
def evaluate(*args, **kwargs):
    assert getattr(generator._cloud, 'on', False), 'TASK-366 retry did not select cloud-only models'
    return {'ok': True, 'preview': [{'recommendation': 'skip', 'fit_score': 40}]}
job_evaluator.evaluate_jobs = evaluate

def generate(*args, **kwargs):
    # TASK-366: compare all generator inputs except the per-attempt progress/cancellation callbacks.
    inputs = repr((args[:9], args[10:], {k: v for k, v in kwargs.items() if k != 'cancelled'}))
    calls.append(inputs)
    args[9](15, 'Generating')  # TASK-366: real task progress transitions to running on both attempts.
    if len(calls) == 1:
        failure = generator._provider_failure('PRIVATE PROMPT\nprovider banner\nERROR: You have hit your usage limit. Visit https://example.invalid/upgrade or try again at 7:27 PM.')
        failure.reset_at = timezone.now() - timedelta(seconds=48)  # TASK-366: real reset+minute timer fires in 12 s.
        raise failure
    assert calls[0] == inputs, 'Automatic retry changed generation inputs'
    until = time.monotonic() + 60
    while not kwargs['cancelled']() and not stopping.is_set():
        assert time.monotonic() < until, 'Cancellation fixture timed out'
        time.sleep(.05)
    raise generator.GenerationCancelled
cv_tasks.generate_cv_package = generate
cv_tasks._retry_missing_source = lambda job: None

server = ThreadedWSGIServer(('127.0.0.1', int(sys.argv[2])), WSGIRequestHandler)
server.set_app(get_wsgi_application())
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()
print(json.dumps({'ready': True, 'jobs': [job.pk for job in jobs]}), flush=True)
try:
    for line in sys.stdin:
        command = json.loads(line)['command']
        if command == 'analysis':
            prep.start_pipeline(jobs[0].pk, user, force=True)
        elif command == 'release':
            release.set()
        elif command == 'evidence':
            print(json.dumps({'calls': len(calls), 'identical': len(calls) == 2 and calls[0] == calls[1]}), flush=True)
        elif command == 'stop':
            break
finally:
    stopping.set()
    release.set()
    for task_id in list(cv_tasks._tasks):
        cv_tasks.cancel_cv_task(task_id, user.pk)
    if prep._timer:
        prep._timer[1].cancel()
    server.shutdown()
    server.server_close()
    thread.join(5)
    for worker in list(threading.enumerate()):
        if worker.name.startswith(('dachapply', 'cv-agent-')) and worker is not threading.current_thread():
            worker.join(5)
            assert not worker.is_alive(), f'TASK-366 worker did not stop: {worker.name}'
