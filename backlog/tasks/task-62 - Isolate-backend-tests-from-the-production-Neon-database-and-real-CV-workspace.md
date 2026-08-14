---
id: TASK-62
title: Isolate backend tests from the production Neon database and real CV workspace
status: Done
assignee:
  - '@claude'
created_date: '2026-08-13 21:43'
updated_date: '2026-08-14 16:35'
labels:
  - bug
  - testing
  - infrastructure
dependencies: []
priority: high
ordinal: 67000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The backend suite runs against the production Neon Postgres host via DATABASE_URL and creates its test database (test_neondb) there. Neon's connection pooler prevents Django from dropping a leftover test database, so any interrupted run poisons every later run with psycopg.errors.DuplicateDatabase until --reuse-db is passed. A clean run takes 8-11 minutes over the network; with --reuse-db it takes about 4 minutes. Separately, test_candidate_evidence_is_required_and_loaded overrides settings.CODEX_CANDIDATE_EVIDENCE_PATH but not settings.CODEX_CV_WORKSPACE, so running the suite overwrites the real C:/latex/.dachapply-cache/candidate-evidence-compact.md with a 17-byte fixture. That snapshot is write-only debug output regenerated from source on the next generation, so there is no generation-quality impact, but tests must not write into the live workspace. Both issues were observed during the TASK-61 session.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Backend tests use a local or disposable database instead of creating a test database on the production Neon instance
- [x] #2 An interrupted run cannot poison subsequent runs
- [x] #3 No test writes into the real CODEX_CV_WORKSPACE; tests that touch it override the setting to a tmp_path
- [x] #4 The documented test command runs green from a cold start with no manual flags
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Added backend/config/settings_test.py and pointed pytest.ini at it (DJANGO_SETTINGS_MODULE=config.settings_test). config/settings.py is byte-identical - production database resolution is untouched.

The mechanism: config.settings reads DATABASE_URL at import time, and load_env_file() applies the repo-root .env via os.environ.setdefault, so a variable that is already set wins. settings_test.py therefore assigns os.environ['DATABASE_URL']='' and defaults DEBUG=1 BEFORE `from .settings import *`, forcing the sqlite fallback branch on every machine regardless of whether dj-database-url is installed. It then pins DATABASES to sqlite ':memory:' outright rather than trusting that fallback (which still honours DB_ENGINE/DB_NAME), and pins CODEX_CV_WORKSPACE to a fresh tempfile.mkdtemp() directory. No new dependency was added.

AC1 verified: under config.settings_test the resolved config is ENGINE=django.db.backends.sqlite3, NAME=':memory:', HOST='' - no Neon host is reachable.
AC2 verified by construction: an in-memory database evaporates with the process, so there is no leftover test_neondb and DuplicateDatabase cannot occur. --reuse-db is no longer needed for anything.
AC3 verified two ways: settings_test pins the workspace to a temp dir so a test that forgets its own override still cannot reach C:/latex, and test_candidate_evidence_is_required_and_loaded (the specific offender named in this task) now overrides settings.CODEX_CV_WORKSPACE to tmp_path. After a full suite run, every file in C:/latex/.dachapply-cache still carried its previous day's mtime, and no cv-benchmarks.jsonl was created there.
AC4 verified: the documented command from AGENTS.md:33 / README.md:133 - `cd backend && python -m pytest -q` - ran in a shell with DATABASE_URL and DEBUG both unset: 148 passed in 39.51s. Previously 8-11 minutes over the network, or ~4 with --reuse-db.

Bypass check: with DATABASE_URL deliberately set to a fake Neon URL in the environment, config.settings_test still resolved to sqlite ':memory:' - the isolation does not depend on the developer remembering to unset anything.

Pre-existing, not fixed here: C:/latex/.dachapply-cache/candidate-evidence-compact.md is still the 17-byte fixture written by the 13-Aug run described above. It is write-only debug output regenerated from source on the next generation, so it needs no repair, but it will stay stale until the next real generation. Also unrelated: a background demo_scheduler.seed_demo_if_due thread raises a caught "Database access not allowed" during test runs; harmless, pre-existing, not in this task's scope.
<!-- SECTION:NOTES:END -->
