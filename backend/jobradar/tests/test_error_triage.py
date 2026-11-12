# TASK-372.2: hermetic CLI boundary; never create real Backlog files.
import importlib
import io
import json
import subprocess
from contextlib import closing
from types import SimpleNamespace

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from jobradar.services import error_occurrences as errors, error_triage as triage
from jobradar.tests.test_error_occurrences import store


@pytest.fixture
def cli(monkeypatch):
    tasks, calls = [], []
    def run(args, **kwargs):
        calls.append(args)
        assert kwargs['cwd'] == triage.ROOT and kwargs['check']
        if args[1:3] == ['task', 'list']:
            return SimpleNamespace(stdout=json.dumps({'tasks': tasks}))
        if args[2] == 'create':
            tasks.append({'id': 'TASK-999', 'title': args[3]})
        return SimpleNamespace(stdout='')
    monkeypatch.setattr(subprocess, 'run', run)
    return tasks, calls


def ingest(identity, **extra):
    return errors.ingest('backend', [dict(id=identity, operation='same', status='failed', classification='actionable', **extra)])[0]


def test_group_incremental_restart_and_private_links(store, cli):
    first = ingest('1')
    ingest('2')
    result = triage.triage()
    assert len(result) == 1 and result[0]['count'] == 2 and result[0]['task_id'] == 'TASK-999'
    count = len(cli[1])
    importlib.reload(triage)
    assert triage.triage() == [] and len(cli[1]) == count
    ingest('3')
    assert triage.triage()[0]['action'] == 'update'
    assert len([c for c in cli[1] if c[2] == 'create']) == 1
    with closing(errors._connect()) as db:
        assert db.execute('SELECT evidence FROM error_group_links WHERE occurrence_id=?', (first,)).fetchone()[0] == 'occurrence:' + first
    assert triage.triage(list_only=True)[0]['task_id'] == 'TASK-999'


def test_build_and_operation_separate_groups_and_resolved_excluded(store, cli):
    first = ingest('1', build='build-a')
    ingest('2', build='build-b')
    errors.ingest('backend', [dict(id='3', operation='other', status='failed')])
    with closing(errors._connect()) as db, db:
        db.execute('UPDATE occurrences SET resolved=1 WHERE id=?', (first,))
    rows = triage.triage(dry_run=True)
    assert len(rows) == 2 and all(r['count'] == 1 for r in rows)
    assert not cli[1]
    with closing(errors._connect()) as db:
        assert db.execute('SELECT count(*) FROM error_groups').fetchone()[0] == 0


@pytest.mark.parametrize('classification', triage.DISPOSITIONS)
def test_dispositions(store, cli, classification):
    errors.ingest('provider', [dict(id='1', status='failed', classification=classification)])
    row = triage.triage()[0]
    assert row['classification'] == classification and row['disposition']
    assert bool(cli[0]) == (classification in ('actionable', 'retry_exhausted'))
    assert triage.triage() == []
    assert len(triage.triage(list_only=True)) == 1


def test_redaction_and_bug_content(store, cli):
    secret = 'Bearer secret CV mail postgres://password /private/log'
    ingest(secret, build=secret, summary=secret, evidence=secret, error_type=secret)
    triage.triage()
    created = next(c for c in cli[1] if c[2] == 'create')
    assert secret not in json.dumps(cli[1])
    description = created[created.index('--description') + 1]
    for text in ('Source:', 'Environment/build/operation', '1 unresolved', 'UTC', 'Reproduction steps: unknown', 'Root cause: unknown'):
        assert text in description
    assert created.count('--ac') == 2
    assert 'occurrence:' not in description


@pytest.mark.parametrize('partial', [False, True])
def test_cli_failure_and_partial_creation_recovery(store, cli, monkeypatch, partial):
    ingest('1')
    original = subprocess.run
    def fail(args, **kwargs):
        if args[2] == 'create':
            if partial:
                original(args, **kwargs)
            raise subprocess.TimeoutExpired(args, 60)
        return original(args, **kwargs)
    monkeypatch.setattr(subprocess, 'run', fail)
    with pytest.raises(subprocess.TimeoutExpired):
        triage.triage()
    with closing(errors._connect()) as db:
        assert db.execute('SELECT count(*) FROM error_groups').fetchone()[0] == 0
    monkeypatch.setattr(subprocess, 'run', original)
    assert triage.triage()[0]['task_id'] == 'TASK-999'
    assert len(cli[0]) == 1


def test_changed_classification_and_command(store, cli):
    errors.ingest('backend', [dict(id='1', operation='same', status='failed', classification='transient')])
    triage.triage()
    with closing(errors._connect()) as db, db:
        db.execute("UPDATE occurrence_context SET classification='retry_exhausted'")
    output = io.StringIO()
    call_command('triage_errors', '--dry-run', stdout=output)
    assert json.loads(output.getvalue())[0]['action'] == 'create'
    assert not cli[0]
    call_command('triage_errors', stdout=io.StringIO())
    assert len(cli[0]) == 1
    call_command('triage_errors', '--list', stdout=io.StringIO())


def test_command_failure_is_sanitized(settings):
    settings.ERROR_OCCURRENCE_LOCAL_DB = ''
    with pytest.raises(CommandError, match='checkpoint retained') as error:
        call_command('triage_errors')
    assert 'Traceback' not in str(error.value)


def test_failed_update_keeps_checkpoint_and_retries(store, cli, monkeypatch):
    ingest('1')
    triage.triage()
    ingest('2')
    original = subprocess.run
    def fail(args, **kwargs):
        if args[2] == 'edit':
            raise subprocess.CalledProcessError(1, args, stderr='private diagnostic')
        return original(args, **kwargs)
    monkeypatch.setattr(subprocess, 'run', fail)
    with pytest.raises(subprocess.CalledProcessError):
        triage.triage()
    assert triage.triage(dry_run=True)[0]['count'] == 2
    monkeypatch.setattr(subprocess, 'run', original)
    assert triage.triage()[0]['action'] == 'update'
    assert triage.triage() == []


def test_legacy_rows_and_untrusted_classification(store, cli):
    identity = ingest('1')
    with closing(errors._connect()) as db, db:
        db.execute('DELETE FROM occurrence_context WHERE id=?', (identity,))
    assert triage.triage()[0]['classification'] == 'unknown'
    assert not cli[0]
    errors.ingest('provider', [dict(id='2', status='failed', classification='secret', build='secret')])
    assert triage.triage()[0]['classification'] == 'unknown'


def test_parallel_triagers_create_one_task(store, cli):
    from concurrent.futures import ThreadPoolExecutor
    ingest('1')
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: triage.triage(), range(2)))
    assert sorted(len(r) for r in results) == [0, 1]
    assert len(cli[0]) == 1


def test_update_appends_evidence_and_keeps_the_description(store, cli):
    # TASK-372.2 review: an investigator's description must survive later triage runs.
    tasks, calls = cli
    ingest('1')
    triage.triage()
    ingest('2')
    assert triage.triage()[0]['action'] == 'update'
    edit = [c for c in calls if c[2] == 'edit'][-1]
    assert '--description' not in edit and '--append-notes' in edit
    assert '2 unresolved failures' in edit[edit.index('--append-notes') + 1]
