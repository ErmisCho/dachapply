"""Kill a real disposable runtime in inline analysis, then Retry through HTTP."""
import http.cookiejar
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time
import urllib.request

from jobradar.services.processing_control import Store


def test_daily_inline_analysis_kill_and_http_retry(tmp_path):
    backend = Path(__file__).resolve().parents[2]
    def port():
        with socket.socket() as connection:
            connection.bind(('127.0.0.1', 0))
            return connection.getsockname()[1]
    app_port, control_port = port(), port()
    token = secrets.token_urlsafe(48)
    workspace = tmp_path / 'documents'
    database = tmp_path / 'control.sqlite3'
    environment = dict(os.environ, DJANGO_SETTINGS_MODULE='config.settings_dashboard_test',
        DACHAPPLY_TEST_DATABASE=str(tmp_path / 'app.sqlite3'), DACHAPPLY_TEST_WORKSPACE=str(workspace),
        DACHAPPLY_LOCAL_MAILBOX_LOOP='0', DACHAPPLY_DEMO_SEED_SCHEDULER='0', DACHAPPLY_PREP_QUEUE_RESUME='0',
        DACHAPPLY_CONTROL_DB=str(database), DACHAPPLY_CONTROL_TOKEN=token, DACHAPPLY_INSTANCE=secrets.token_hex(16),
        PYTHONPATH=str(backend))
    for command in ('migrate', 'createcachetable'):
        subprocess.run([sys.executable, 'manage.py', command, '--verbosity', '0'], cwd=backend,
                       env=environment, check=True, capture_output=True, timeout=30)
    fixture = [sys.executable, '-m', 'jobradar.tests.runtime_retry_fixture']
    seed = subprocess.run([*fixture, 'seed'], cwd=backend, env=environment,
                          check=True, capture_output=True, text=True, timeout=30)
    job = json.loads(seed.stdout)['job']
    def control(action='status', method='GET'):
        request = urllib.request.Request(f'http://127.0.0.1:{control_port}/{action}', method=method,
                                        headers={'Authorization': 'Bearer ' + token})
        with urllib.request.urlopen(request, timeout=3) as response:
            return json.load(response)
    process = None
    def until(predicate):
        deadline = time.monotonic() + 30
        while not predicate():
            assert process.poll() is None, 'Disposable runtime exited; see runtime.log'
            assert time.monotonic() < deadline, 'Disposable runtime timed out'
            time.sleep(.1)
    log = (tmp_path / 'runtime.log').open('w', encoding='utf-8')
    def start():
        nonlocal process
        process = subprocess.Popen([*fixture, 'serve', str(app_port), str(control_port)], cwd=backend,
            env=environment, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        def ready():
            try:
                return control()['running']
            except OSError:
                return False
        until(ready)
    try:
        start()
        until(lambda: (workspace / 'analysis-started').exists())
        assert control()['running_jobs'] == 1
        process.kill()  # Only the Popen child owned by this test.
        process.wait(timeout=10)
        (workspace / 'block').unlink()
        start()
        assert control()['interrupted_jobs'] == 1
        jar = http.cookiejar.CookieJar()
        client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
        base = f'http://127.0.0.1:{app_port}'
        with client.open(base + '/api/auth/csrf/') as response:
            response.read()
        def post(path, data):
            csrf = next(cookie.value for cookie in jar if cookie.name == 'csrftoken')
            request = urllib.request.Request(base + path, method='POST', data=json.dumps(data).encode(),
                headers={'Content-Type': 'application/json', 'X-CSRFToken': csrf})
            with client.open(request, timeout=5) as response:
                return json.load(response)
        post('/api/auth/login/', {'username': 'retry-fixture', 'password': 'fixture-password-123'})
        with client.open(base + f'/api/jobs/{job}/application-prep/') as response:
            assert 'stopped before it finished' in json.load(response)['reason']
        post(f'/api/jobs/{job}/application-prep/retry/', {})
        def ready_document():
            with client.open(base + f'/api/jobs/{job}/application-prep/') as response:
                variants = json.load(response)['variants']
            return len(variants) == 1 and variants[0]['status'] == 'ready'
        until(ready_document)
        until(lambda: Store(database).active_units() == 0)
        state = control()
        assert state['interrupted_jobs'] == 0
        assert state['running_jobs'] == state['remaining_jobs'] == 0
        assert state['completed_jobs'] == 2  # Requirements analysis and the generated document.
        assert (workspace / 'fixture.pdf').is_file()
    finally:
        if process is not None and process.poll() is None:
            try:
                control('stop', 'POST')
                process.wait(timeout=15)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=10)
        log.close()
