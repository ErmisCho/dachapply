"""TASK-356: Neon usage tracking. HTTP is faked throughout; nothing here reaches Neon."""
import io
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError

import pytest
from django.contrib.auth.models import User
from django.core import mail
from rest_framework.test import APIClient

from jobradar.services import db_usage

KEY = 'neon-secret-key-value'
OWNER = 'owner@example.test'
GB = 1_000_000_000


def project(transfer=0.0, compute_hours=0, storage=0.0, start='2026-11-01T00:00:00Z'):
    return {'data_transfer_bytes': int(transfer * GB), 'compute_time_seconds': compute_hours * 3600, 'synthetic_storage_size': int(storage * GB),
            'consumption_period_start': start, 'consumption_period_end': '2026-12-01T00:00:00Z'}


@pytest.fixture
def tracking(settings, tmp_path, monkeypatch):
    settings.NEON_API_KEY = KEY
    settings.NEON_PROJECT_ID = 'project-1'
    settings.DB_USAGE_OWNER_EMAIL = OWNER
    monkeypatch.setenv('DACHAPPLY_CONTROL_DB', str(tmp_path / 'control.sqlite3'))
    return tmp_path / 'db-usage.json'


def check(monkeypatch, response):
    monkeypatch.setattr(db_usage, 'fetch_project', lambda: response)
    return db_usage.check()


def subjects():
    return [message.subject for message in mail.outbox]


def test_a_jump_past_several_steps_sends_one_email_naming_the_current_step(tracking, monkeypatch):
    check(monkeypatch, project(transfer=.6))  # 12%
    assert subjects() == ['Neon transfer reached 10%']
    assert mail.outbox[0].to == [OWNER]
    check(monkeypatch, project(transfer=1.35))  # 27%
    assert subjects() == ['Neon transfer reached 10%', 'Neon transfer reached 25%']


def test_a_step_is_sent_once_and_never_again_after_a_restart(tracking, monkeypatch):
    check(monkeypatch, project(transfer=1.0))
    check(monkeypatch, project(transfer=1.1))  # the same 20% step
    state = json.loads(tracking.read_text(encoding='utf-8'))  # what a restart reads back
    assert state['sent'] == {'transfer': 20}
    check(monkeypatch, project(transfer=1.1))
    assert subjects() == ['Neon transfer reached 20%']


def test_below_the_first_step_sends_nothing(tracking, monkeypatch):
    check(monkeypatch, project(transfer=.2, compute_hours=4, storage=.04))
    assert subjects() == []


def test_each_metric_has_its_own_steps(tracking, monkeypatch):
    check(monkeypatch, project(transfer=.5, compute_hours=30, storage=.5))
    assert sorted(subjects()) == ['Neon compute reached 30%', 'Neon storage reached 50%', 'Neon transfer reached 10%']


def test_steps_start_again_in_a_new_billing_period(tracking, monkeypatch):
    check(monkeypatch, project(transfer=1.0))
    check(monkeypatch, project(transfer=1.0, start='2026-12-01T00:00:00Z'))
    assert subjects() == ['Neon transfer reached 20%', 'Neon transfer reached 20%']


def test_a_reformatted_period_start_resends_nothing(tracking, monkeypatch):
    check(monkeypatch, project(transfer=1.0))
    check(monkeypatch, project(transfer=1.0, start='2026-11-01T00:00:00.000Z'))
    assert len(mail.outbox) == 1


def test_a_failed_send_stays_unsent_and_goes_out_once_on_a_later_check(tracking, monkeypatch, caplog):
    real, calls = db_usage.send_mail, []

    def flaky(*args):
        calls.append(args)
        if len(calls) == 1:
            raise OSError(f'smtp refused {KEY}')
        return real(*args)
    monkeypatch.setattr(db_usage, 'send_mail', flaky)
    assert check(monkeypatch, project(transfer=1.0))['sent'] == {}
    assert subjects() == [] and KEY not in caplog.text
    check(monkeypatch, project(transfer=1.0))
    check(monkeypatch, project(transfer=1.0))
    assert subjects() == ['Neon transfer reached 20%']


@pytest.mark.parametrize('response', [{}, {'data_transfer_bytes': 'lots', 'compute_time_seconds': None, 'synthetic_storage_size': True},
                                      {'data_transfer_bytes': float('inf')}, {'data_transfer_bytes': -5}])
def test_missing_or_malformed_fields_are_unknown(tracking, monkeypatch, response):
    state = check(monkeypatch, response)
    assert [metric['percent'] for metric in state['metrics'].values()] == [None, None, None]
    assert [metric['limit'] for metric in state['metrics'].values()] == [5, 100, 1]
    assert subjects() == []


def test_a_check_never_touches_the_database(tracking, monkeypatch):
    # No `db` fixture: pytest-django raises on any database access in this test, and send_mail is real.
    state = check(monkeypatch, project(transfer=1.0, compute_hours=50, storage=.5))
    assert state['sent'] == {'transfer': 20, 'compute': 50, 'storage': 50}


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class Opener:
    def __init__(self, result):
        self.result, self.requests = result, []

    def open(self, request, timeout):
        self.requests.append(request)
        if isinstance(self.result, Exception):
            raise self.result
        return Response(self.result)


def test_the_read_sends_the_key_in_the_header_and_reads_the_project_object(tracking, monkeypatch):
    opener = Opener(json.dumps({'project': project(transfer=1.0)}).encode())
    monkeypatch.setattr(db_usage, 'build_opener', lambda *handlers: opener)
    state = db_usage.check()
    request = opener.requests[0]
    assert request.full_url == 'https://console.neon.tech/api/v2/projects/project-1'
    assert request.get_header('Authorization') == f'Bearer {KEY}'
    assert state['metrics']['transfer'] == {'label': 'Transfer', 'used': 1.0, 'limit': 5, 'unit': 'GB', 'percent': 20.0}
    assert state['period'] == {'start': '2026-11-01T00:00:00Z', 'end': '2026-12-01T00:00:00Z'}


def test_a_redirect_is_never_followed_with_the_key():
    assert db_usage._NoRedirect().redirect_request('request', 'file', 302, 'Found', {}, 'https://elsewhere.test/') is None


@pytest.mark.parametrize('failure,shown', [(HTTPError('https://console.neon.tech', 401, f'bad {KEY}', {}, None), 'Neon answered 401'),
                                           (OSError(f'connection to {KEY} failed'), 'Could not read usage from Neon')])
def test_a_failed_read_keeps_the_numbers_and_never_exposes_the_key(tracking, monkeypatch, caplog, failure, shown):
    check(monkeypatch, project(transfer=1.0))
    monkeypatch.undo()
    monkeypatch.setenv('DACHAPPLY_CONTROL_DB', str(tracking.parent / 'control.sqlite3'))
    monkeypatch.setattr(db_usage, 'build_opener', lambda *handlers: Opener(failure))
    with caplog.at_level(logging.INFO):
        state = db_usage.check()
    assert state['error'] == shown and state['metrics']['transfer']['used'] == 1.0
    assert KEY not in caplog.text and KEY not in tracking.read_text(encoding='utf-8')


def test_no_key_means_off_silently(settings, tmp_path, monkeypatch, caplog):
    monkeypatch.setenv('DACHAPPLY_CONTROL_DB', str(tmp_path / 'control.sqlite3'))
    settings.DB_USAGE_OWNER_EMAIL = OWNER
    monkeypatch.setattr(db_usage, 'Thread', lambda **kwargs: pytest.fail('tracking started without a key'))
    with caplog.at_level(logging.DEBUG):
        db_usage.start()
    assert db_usage.public_state() == {'configured': False}
    assert caplog.text == '' and mail.outbox == []
    assert not (tmp_path / 'db-usage.json').exists()


def test_no_control_database_means_off(settings, monkeypatch):
    settings.NEON_API_KEY, settings.NEON_PROJECT_ID = KEY, 'project-1'
    monkeypatch.delenv('DACHAPPLY_CONTROL_DB', raising=False)
    assert not db_usage.configured()


def test_a_restart_inside_the_hour_waits_out_the_rest_of_it(tracking, monkeypatch):
    assert db_usage.seconds_until_due() == 0
    check(monkeypatch, project())
    assert 3590 < db_usage.seconds_until_due() <= 3600
    state = db_usage.read_state()
    state['attempted_at'] = (datetime.now(timezone.utc) - timedelta(minutes=45)).isoformat()
    tracking.write_text(json.dumps(state), encoding='utf-8')
    assert 890 < db_usage.seconds_until_due() <= 900


def test_the_loop_checks_once_per_hour_even_if_a_check_raises(tracking, monkeypatch):
    sleeps, checks = [], []

    class Stop(Exception):
        pass

    def sleep(seconds):
        sleeps.append(seconds)
        if len(sleeps) == 3:
            raise Stop

    def boom():
        checks.append(1)
        raise OSError('boom')
    monkeypatch.setattr(db_usage.time, 'sleep', sleep)
    monkeypatch.setattr(db_usage, 'check', boom)
    with pytest.raises(Stop):
        db_usage._loop()
    assert sleeps == [0, 3600, 3600] and len(checks) == 2


def test_only_the_dashboard_runtime_starts_tracking():
    root = Path(db_usage.__file__).parents[1]
    starters = [path.name for path in root.rglob('*.py') if 'db_usage.start(' in path.read_text(encoding='utf-8') and 'tests' not in path.parts]
    assert starters == ['dashboard_runtime.py']


# --- the owner-only endpoint ---------------------------------------------------------------------

def _client(email):
    user = User.objects.create_user(email.split('@')[0], email=email, password='pw')
    client = APIClient()
    client.force_authenticate(user)
    return client


@pytest.mark.django_db
def test_the_panel_is_for_the_configured_account_in_any_case(tracking, monkeypatch):
    check(monkeypatch, project(transfer=1.0))
    response = _client('OWNER@Example.Test').get('/api/db-usage/')
    assert response.status_code == 200
    assert response.data['configured'] is True and response.data['metrics']['transfer']['percent'] == 20.0
    assert KEY not in response.content.decode()


@pytest.mark.django_db
def test_any_other_account_gets_nothing(tracking, monkeypatch):
    check(monkeypatch, project(transfer=1.0))
    assert _client('someone@example.test').get('/api/db-usage/').status_code == 404
    assert APIClient().get('/api/db-usage/').status_code in (401, 403)


@pytest.mark.django_db
def test_no_owner_configured_means_nobody_sees_it(settings):
    settings.DB_USAGE_OWNER_EMAIL = ''
    assert _client('blank@example.test').get('/api/db-usage/').status_code == 404


@pytest.mark.django_db
def test_the_panel_says_not_configured(settings, monkeypatch):
    settings.DB_USAGE_OWNER_EMAIL = OWNER
    assert _client(OWNER).get('/api/db-usage/').data == {'configured': False}


@pytest.mark.django_db
def test_the_endpoint_issues_no_query(tracking, monkeypatch, django_assert_num_queries):
    check(monkeypatch, project(transfer=1.0))
    client = _client(OWNER)
    with django_assert_num_queries(0):
        assert client.get('/api/db-usage/').status_code == 200


@pytest.mark.django_db
def test_me_flags_only_the_owner(settings):
    settings.DB_USAGE_OWNER_EMAIL = OWNER
    assert _client(OWNER).get('/api/auth/me/').data['can_view_db_usage'] is True
    assert _client('other@example.test').get('/api/auth/me/').data['can_view_db_usage'] is False
