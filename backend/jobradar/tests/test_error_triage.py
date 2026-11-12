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
            return SimpleNamespace(stdout=json.dumps({'tasks': [t for t in tasks if args[args.index('--search') + 1] in t['title']]}))
        if args[2] == 'view':  # TASK-372.3
            return SimpleNamespace(stdout=json.dumps({'task': next(t for t in tasks if t['id'] == args[3])}))
        if args[2] == 'create':
            tasks.append({'id': 'TASK-' + str(999 + len(tasks)), 'title': args[3], 'type': 'bug', 'status': 'To Do'})
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
        if args[2] == 'view':  # TASK-372.3
            return SimpleNamespace(stdout=json.dumps({'task': next(t for t in tasks if t['id'] == args[3])}))
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


# TASK-372.3: all completion/status calls are hermetic; references attest the policy gates.
def complete(task_id='TASK-999'):
    return triage.resolve(task_id, fix='commit:abc', tests='report:passed',
                          evaluation='report:PERFECT', merge='squash:abc', fixed_build='fixed')


def test_resolution_lifecycle_interrupted_sync_and_regression(store, cli, monkeypatch):
    first = ingest('old', build='old')
    triage.triage()
    with pytest.raises(ValueError):
        complete()
    cli[0][0]['status'] = 'Done'
    late = ingest('during-closure', build='fixed')  # Unlinked, even though already collected.
    original = subprocess.run
    def interrupted(args, **kwargs):
        if args[2] == 'view':
            raise subprocess.TimeoutExpired(args, 60)
        return original(args, **kwargs)
    monkeypatch.setattr(subprocess, 'run', interrupted)
    with pytest.raises(subprocess.TimeoutExpired):
        complete()
    assert {r['id'] for r in errors.unresolved()} == {first, late}
    monkeypatch.setattr(subprocess, 'run', original)
    assert complete() == [first]
    assert complete() == []
    with closing(errors._connect()) as db:
        assert db.execute('SELECT count(*) FROM error_group_links').fetchone()[0] == 1
        assert json.loads(db.execute('SELECT verification FROM error_resolutions').fetchone()[0])['evaluation'] == 'report:PERFECT'
        assert db.execute('SELECT evidence FROM occurrences WHERE id=?', (first,)).fetchone()[0] == 'occurrence:' + first
    importlib.reload(errors)
    importlib.reload(triage)
    assert ingest('old', build='old') == first
    rows = triage.triage()
    assert len(rows) == 1 and 'pre-fix evidence' in rows[0]['disposition']
    regression = ingest('new-generation:1', build='fixed')
    row = triage.triage()[0]
    assert 'post-fix regression' in row['disposition'] and row['task_id'] != 'TASK-999'
    assert regression in {r['id'] for r in errors.unresolved()}
    calls = len(cli[1])
    assert ingest('new-generation:1', build='fixed') == regression
    assert triage.triage() == [] and len(cli[1]) == calls
    ingest('old-runtime-new-event', build='old')
    assert 'unfixed or unknown' in triage.triage()[0]['disposition']


def test_resolved_replay_has_no_analysis_and_command_requires_references(store, cli):
    first = ingest('old')
    triage.triage()
    cli[0][0]['status'] = 'Done'
    with pytest.raises(CommandError):
        call_command('triage_errors', '--resolve', 'TASK-999')
    call_command('triage_errors', '--resolve', 'TASK-999', '--fix', 'commit', '--tests', 'passed',
                 '--evaluation', 'PERFECT', '--merge', 'squash', '--fixed-build', 'fixed', stdout=io.StringIO())
    importlib.reload(triage)
    assert ingest('old') == first
    count = len(cli[1])
    assert triage.triage() == [] and len(cli[1]) == count


# TASK-372.3: intake that races status lookup commits after closure and stays unresolved.
def test_resolution_serializes_concurrent_arrival(store, cli, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    first = ingest('first', build='old')
    triage.triage()
    cli[0][0]['status'] = 'Done'
    original, started = subprocess.run, Event()
    def arrival():
        started.set()
        return ingest('concurrent', build='fixed')
    with ThreadPoolExecutor(max_workers=1) as pool:
        futures = []
        def status(args, **kwargs):
            if args[2] == 'view':
                futures.append(pool.submit(arrival))
                assert started.wait(1)
            return original(args, **kwargs)
        monkeypatch.setattr(subprocess, 'run', status)
        assert complete() == [first]
        later = futures[0].result()
    assert [r['id'] for r in errors.unresolved()] == [later]
    assert 'post-fix regression' in triage.triage()[0]['disposition']


def test_regression_create_interruption_recovers_one_successor(store, cli, monkeypatch):
    ingest('first', build='old')
    triage.triage()
    cli[0][0]['status'] = 'Done'
    complete()
    ingest('regression', build='fixed')
    original = subprocess.run
    def interrupted(args, **kwargs):
        result = original(args, **kwargs)
        if args[2] == 'create':
            raise subprocess.TimeoutExpired(args, 60)
        return result
    monkeypatch.setattr(subprocess, 'run', interrupted)
    with pytest.raises(subprocess.TimeoutExpired):
        triage.triage()
    monkeypatch.setattr(subprocess, 'run', original)
    assert triage.triage()[0]['task_id'] == 'TASK-1000'
    assert len(cli[0]) == 2 and triage.triage() == []


def test_later_family_closure_cannot_duplicate_an_interrupted_successor(store, cli, monkeypatch):
    # TASK-372.3 review: a closure made after the regression arrived must not change its successor marker.
    tasks = cli[0]
    ingest('first', build='old')
    ingest('other', build='other')
    triage.triage()
    first, other = (t['id'] for t in tasks)
    tasks[0]['status'] = 'Done'
    complete(first)
    ingest('regression', build='fixed')
    original = subprocess.run
    def interrupted(args, **kwargs):
        result = original(args, **kwargs)
        if args[2] == 'create':
            raise subprocess.TimeoutExpired(args, 60)
        return result
    monkeypatch.setattr(subprocess, 'run', interrupted)
    with pytest.raises(subprocess.TimeoutExpired):
        triage.triage()
    monkeypatch.setattr(subprocess, 'run', original)
    tasks[1]['status'] = 'Done'
    complete(other)
    triage.triage()
    assert len(tasks) == 3 and triage.triage() == []
