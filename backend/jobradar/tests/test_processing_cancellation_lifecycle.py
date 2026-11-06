"""No mocked server/compiler: exercise HTTP cancellation across real Stop/Start/Resume."""
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


def test_cancelled_document_stays_cancelled_after_graceful_restart(tmp_path):
    backend = Path(__file__).resolve().parents[2]
    def port():
        with socket.socket() as connection:
            connection.bind(('127.0.0.1', 0))
            return connection.getsockname()[1]
    app_port, control_port = port(), port()
    token = secrets.token_urlsafe(48)
    database = tmp_path / 'processing.sqlite3'
    environment = dict(os.environ, DJANGO_SETTINGS_MODULE='config.settings_dashboard_test',
        DACHAPPLY_TEST_DATABASE=str(tmp_path / 'app.sqlite3'), DACHAPPLY_TEST_WORKSPACE=str(tmp_path / 'documents'),
        DACHAPPLY_LOCAL_MAILBOX_LOOP='0', DACHAPPLY_DEMO_SEED_SCHEDULER='0', DACHAPPLY_PREP_QUEUE_RESUME='0',
        DACHAPPLY_CONTROL_DB=str(database), DACHAPPLY_CONTROL_TOKEN=token, DACHAPPLY_INSTANCE=secrets.token_hex(16))
    environment['PYTHONPATH'] = str(backend)
    for command in ('migrate', 'createcachetable'):
        subprocess.run([sys.executable, 'manage.py', command, '--verbosity', '0'], cwd=backend,
                       env=environment, check=True, capture_output=True)
    def control(action='status', method='GET'):
        request = urllib.request.Request(f'http://127.0.0.1:{control_port}/{action}', method=method,
                                        headers={'Authorization': 'Bearer ' + token})
        with urllib.request.urlopen(request, timeout=3) as response:
            return json.load(response)
    def until(predicate):
        deadline = time.monotonic() + 30
        while not predicate():
            assert time.monotonic() < deadline, 'Disposable runtime timed out'
            time.sleep(.1)
    process = None
    def start():
        nonlocal process
        # Same controller Start semantics: restore a deliberately stopped queue paused.
        state = Store(database)
        if state.mode() == 'stopping':
            state.mode('paused')
        process = subprocess.Popen([sys.executable, 'manage.py', 'dashboard_runtime', '--port', str(app_port),
            '--control-port', str(control_port)], cwd=backend, env=environment, stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        def ready():
            assert process.poll() is None, 'Disposable runtime exited'
            try:
                return control()['running']
            except OSError:
                return False
        until(ready)
    def stop():
        control('stop', 'POST')
        process.wait(timeout=30)
    try:
        start()
        control('pause', 'POST')
        seed = subprocess.run([sys.executable, '-m', 'jobradar.tests.runtime_cancel_seed'], cwd=backend,
                              env=environment, capture_output=True, text=True, check=True)
        task_id = json.loads(seed.stdout)['task']
        stop(); start()
        jar = http.cookiejar.CookieJar()
        client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
        base = f'http://127.0.0.1:{app_port}'
        with client.open(base + '/api/auth/csrf/') as response:
            response.read()
        def post(path, data):
            csrf = next(cookie.value for cookie in jar if cookie.name == 'csrftoken')
            request = urllib.request.Request(base + path, method='POST', data=json.dumps(data).encode(),
                headers={'Content-Type': 'application/json', 'X-CSRFToken': csrf})
            with client.open(request) as response:
                return response.status, json.load(response)
        post('/api/auth/login/', {'username': 'cancel-fixture', 'password': 'fixture-password-123'})
        code, task = post(f'/api/cv-generation/tasks/{task_id}/cancel/', {})
        assert code == 202 and task['status'] == 'cancelling'
        stop(); start()
        with client.open(base + f'/api/cv-generation/tasks/{task_id}/') as response:
            assert json.load(response)['status'] == 'cancelling'
        control('resume', 'POST')
        until(lambda: control()['running_jobs'] == 0 and control()['remaining_jobs'] == 0)
        with client.open(base + f'/api/cv-generation/tasks/{task_id}/') as response:
            assert json.load(response)['status'] == 'cancelled'
        state = control()
        assert state['cancelled_jobs'] == 1
        assert state['completed_jobs'] == 0 and state['failed_jobs'] == 0
        assert not (tmp_path / 'documents/cancelled.pdf').exists()
    finally:
        if process is not None and process.poll() is None:
            stop()
