"""TASK-100: a manage.py run locally must not be able to silently reach production.

config.settings applies its guard at module import time (it has to -- DATABASES is built at import),
so it cannot be exercised end-to-end by reimporting the module inside the hermetic test process
without fighting Django's already-configured settings. What is tested here is the two pieces that
decide the outcome, both plain functions with no import-time side effects:

- load_env_file(): does it correctly report which keys it actually populated from a file, as
  opposed to keys the process environment already had -- per the frozen `_process_env_keys`
  snapshot, not the live, mutable os.environ (see the "immune to its own writes" test below for why
  that distinction is the whole point: it is what survived Django's actual retry-poisoning bug,
  caught while closing this task -- see settings.py's comment on _ENV_SNAPSHOT_MARKER)?
- local_db_guard_blocks(): given that report, does it block exactly the file-sourced,
  no-opt-in case and nothing else -- including failing closed on a garbage opt-in value?

The real end-to-end behaviour (settings.py actually refusing to import against the real repo-root
.env, and the container/CI shape actually working) is measured directly with a real manage.py
subprocess as part of closing this task, not simulated here.
"""
import config.settings as settings_module
from config.settings import env_bool, load_env_file, local_db_guard_blocks


def test_load_env_file_reports_keys_not_in_the_process_snapshot(tmp_path, monkeypatch):
    monkeypatch.setattr(settings_module, '_process_env_keys', frozenset({'PATH'}))
    env_path = tmp_path / '.env'
    env_path.write_text('DATABASE_URL=postgresql://prod-host/db\nPATH=ignored\n', encoding='utf-8')

    keys = load_env_file(env_path)

    assert keys == {'DATABASE_URL'}  # PATH was in the snapshot, DATABASE_URL was not


def test_load_env_file_excludes_keys_the_snapshot_already_had(tmp_path, monkeypatch):
    monkeypatch.setattr(settings_module, '_process_env_keys', frozenset({'DATABASE_URL'}))
    env_path = tmp_path / '.env'
    env_path.write_text('DATABASE_URL=postgresql://prod-host/db\n', encoding='utf-8')

    keys = load_env_file(env_path)

    assert 'DATABASE_URL' not in keys


def test_load_env_file_is_immune_to_its_own_earlier_os_environ_writes(tmp_path, monkeypatch):
    """Regression test for the actual bug found while closing this task.

    Django's LazySettings retries importing config.settings on every failed attribute access, and a
    module that raised is dropped from sys.modules, so a guard raise here means config.settings
    re-executes from scratch -- but os.environ is a real process-global and does NOT get rolled
    back. A version of load_env_file() that asked "is this key already in os.environ" (rather than
    "was it in the pre-module snapshot") would see DATABASE_URL as pre-existing on the retry, since
    its own first pass had just written it there, and would stop reporting it as file-sourced --
    silently defeating the guard on the very next settings access. Measured against the real repo
    root .env: manage.py check crashed with AppRegistryNotReady, a Django-internals symptom of this
    exact defeat, before the fix.
    """
    monkeypatch.setattr(settings_module, '_process_env_keys', frozenset())  # nothing pre-existing
    monkeypatch.setenv('DATABASE_URL', 'postgresql://prod-host/db')  # simulates the first pass's write
    env_path = tmp_path / '.env'
    env_path.write_text('DATABASE_URL=postgresql://prod-host/db\n', encoding='utf-8')

    keys = load_env_file(env_path)

    assert 'DATABASE_URL' in keys


def test_load_env_file_missing_file_returns_empty_set(tmp_path):
    assert load_env_file(tmp_path / 'does-not-exist.env') == set()


def test_guard_blocks_file_sourced_database_url_with_no_opt_in():
    assert local_db_guard_blocks(
        'postgresql://prod-host/db', {'DATABASE_URL'}, allow_prod_db=False
    ) is True


def test_guard_allows_file_sourced_database_url_with_explicit_opt_in():
    assert local_db_guard_blocks(
        'postgresql://prod-host/db', {'DATABASE_URL'}, allow_prod_db=True
    ) is False


def test_guard_allows_database_url_typed_this_session():
    """Not in file_sourced_keys means the shell set it, e.g. `DATABASE_URL=... uv run manage.py ...`."""
    assert local_db_guard_blocks(
        'postgresql://prod-host/db', file_sourced_keys=set(), allow_prod_db=False
    ) is False


def test_guard_allows_empty_database_url_regardless_of_source():
    """The documented DATABASE_URL='' + DB_NAME=... workaround: falsy value, nothing to block."""
    assert local_db_guard_blocks('', {'DATABASE_URL'}, allow_prod_db=False) is False


def test_guard_fails_closed_on_garbage_opt_in_value(monkeypatch):
    for garbage in ('', 'nope', 'DACHAPPLY_ALLOW_PROD_DB', '0', 'false'):
        monkeypatch.setenv('DACHAPPLY_ALLOW_PROD_DB', garbage)
        allow_prod_db = env_bool('DACHAPPLY_ALLOW_PROD_DB', False)
        assert local_db_guard_blocks(
            'postgresql://prod-host/db', {'DATABASE_URL'}, allow_prod_db
        ) is True, f'garbage opt-in value {garbage!r} must not grant production access'


def test_guard_opens_on_recognized_truthy_opt_in_values(monkeypatch):
    for truthy in ('1', 'true', 'True', 'yes', 'on'):
        monkeypatch.setenv('DACHAPPLY_ALLOW_PROD_DB', truthy)
        allow_prod_db = env_bool('DACHAPPLY_ALLOW_PROD_DB', False)
        assert local_db_guard_blocks(
            'postgresql://prod-host/db', {'DATABASE_URL'}, allow_prod_db
        ) is False, f'opt-in value {truthy!r} should have been accepted'
