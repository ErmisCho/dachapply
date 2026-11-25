"""TASK-406.3: the owner-only failure page API."""
import json

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from jobradar.services import fix_runs

OWNER = 'owner@example.test'
SIG = 'a' * 64


@pytest.fixture
def logs(settings, tmp_path, monkeypatch):
    settings.DEBUG, settings.CODEX_CV_WORKSPACE, settings.CODEX_CV_OWNER_EMAIL = True, str(tmp_path), OWNER
    (tmp_path/'.dachapply-logs'/'failures').mkdir(parents=True)
    (tmp_path/'.dachapply-logs'/'failed').mkdir()
    (tmp_path/'secret.txt').write_text('outside', encoding='utf-8')
    monkeypatch.setattr(fix_runs, 'status', lambda: {'enabled': True, 'reason': ''})
    monkeypatch.setattr(fix_runs, 'runs', lambda: [{'id': 'r1', 'signature': SIG, 'state': 'running', 'task_id': 'TASK-9'}])
    return tmp_path/'.dachapply-logs'


def client(email=OWNER, **extra):
    user = User.objects.get_or_create(username=email, defaults={'email': email})[0]
    api = APIClient(**extra)
    api.force_authenticate(user)
    return api


def save(logs, name, signature=SIG, files=(), klass='actionable', time='2026-11-20T10:00:00+01:00', user=None):
    owner = user or User.objects.get_or_create(username=OWNER, defaults={'email': OWNER})[0]
    (logs/'failures'/f'{name}.json').write_text(json.dumps({'id': name, 'time': time, 'job_id': 1, 'user_id': owner.id, 'error': 'e', 'diagnostics': 'd', 'cause': 'Bad TeX',
                                                           'signature': signature, 'class': klass, 'files': [str(f) for f in files]}), encoding='utf-8')


@pytest.mark.django_db
def test_owner_only_and_not_in_production(logs, settings):
    save(logs, 'one')
    assert client().get('/api/failures/').status_code == 200
    assert client('other@example.test').get('/api/failures/').status_code == 404
    assert client('other@example.test').get(f'/api/failures/{SIG}/').status_code == 404
    settings.DEBUG = False
    assert client().get('/api/failures/').status_code == 404
    assert client().get(f'/api/failures/{SIG}/').status_code == 404


@pytest.mark.django_db
def test_groups_count_state_and_run(logs):
    save(logs, 'one'); save(logs, 'two', time='2026-11-21T10:00:00+01:00')
    save(logs, 'three', signature='b' * 64, klass='quota'); save(logs, 'four', signature='c' * 64, klass='unknown')
    data = client().get('/api/failures/').data
    by = {g['signature'][0]: g for g in data['groups']}
    assert (by['a']['count'], by['a']['last'], by['a']['state'], by['a']['task_id'], by['a']['run']['id']) == (2, '2026-11-21T10:00:00+01:00', 'running', 'TASK-9', 'r1')
    assert (by['b']['state'], by['c']['state'], by['b']['run']) == ('not_a_bug', 'look', None)
    assert data['fix'] == {'enabled': True, 'reason': ''}


@pytest.mark.django_db
def test_a_run_saved_without_a_pr_links_no_task(logs, monkeypatch):  # TASK-413: runs saved before the fix too
    save(logs, 'one')
    monkeypatch.setattr(fix_runs, 'runs', lambda: [{'id': 'r1', 'signature': SIG, 'state': 'failed', 'task_id': 'TASK-413'}])
    group = client().get('/api/failures/').data['groups'][0]
    assert group['task_id'] == '' and group['run']['task_id'] == ''


@pytest.mark.django_db
def test_files_inside_failed_only(logs):
    inside = logs/'failed'/'a.tex'
    inside.write_text('\documentclass', encoding='utf-8')
    big = logs/'failed'/'big.tex'
    big.write_text('x' * 300_000, encoding='utf-8')
    dotted = logs/'failed'/'..'/'..'/'secret.txt'
    save(logs, 'one', files=[inside, big, logs.parent/'secret.txt', dotted, logs/'failures'/'one.json', logs/'failed'/'gone.tex'])
    files = client().get(f'/api/failures/{SIG}/').data['records'][0]['files']
    assert files[0] == {'name': 'a.tex', 'text': '\documentclass'}
    assert len(files[1]['text']) == 200_000
    assert [f['text'] for f in files[2:]] == [None] * 4
    assert 'secret' not in json.dumps(files).replace('secret.txt', '') and str(logs) not in json.dumps(files)


@pytest.mark.django_db
def test_fix_only_from_this_machine(logs, monkeypatch, settings):
    settings.ALLOWED_HOSTS = ['*']
    started = []
    monkeypatch.setattr(fix_runs, 'start', lambda sig, user: started.append(sig) or {'id': 'r2'})
    url = f'/api/failures/{SIG}/fix/'
    assert client(REMOTE_ADDR='100.64.0.2').post(url).status_code == 403
    assert client(HTTP_X_FORWARDED_FOR='1.2.3.4').post(url).status_code == 403
    assert client(HTTP_TAILSCALE_USER_LOGIN='x').post(url).status_code == 403
    assert client(HTTP_HOST='myhost.tailnet.ts.net').post(url).status_code == 403
    assert not started
    assert client(HTTP_HOST='localhost:8000').post(url).status_code == 202 and started == [SIG]
    assert client('other@example.test').post(url).status_code == 404


@pytest.mark.django_db
def test_value_error_is_400(logs):
    def refuse(*args):
        raise ValueError('Not allowed now.')
    from unittest import mock
    with mock.patch.object(fix_runs, 'start', refuse), mock.patch.object(fix_runs, 'stop', refuse):
        for response in (client(HTTP_HOST='localhost').post(f'/api/failures/{SIG}/fix/'), client().post('/api/failures/runs/r1/stop/')):
            assert (response.status_code, response.data['detail']) == (400, 'Not allowed now.')


@pytest.mark.django_db
def test_me_flag(logs, settings):
    assert client().get('/api/auth/me/').data['can_view_failures'] is True
    assert client('other@example.test').get('/api/auth/me/').data['can_view_failures'] is False
