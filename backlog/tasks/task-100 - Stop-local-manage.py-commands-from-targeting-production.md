---
id: TASK-100
title: Stop local manage.py commands from targeting production
status: Done
assignee:
  - '@agent'
created_date: '2026-08-16 12:10'
updated_date: '2026-08-16 16:40'
labels:
  - backend
  - safety
  - dx
dependencies: []
modified_files:
  - backend/config/settings.py
  - backend/jobradar/tests/test_local_db_guard.py
  - README.md
  - .env.example
  - .env.local.example
  - .env.local-neon.example
  - .env.local-one-server.example
priority: high
ordinal: 101000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`backend/config/settings.py:21` calls `load_env_file(BASE_DIR.parent / '.env')`, and the repo-root
`.env` holds the production Neon `DATABASE_URL`. So **any** `manage.py` command run locally targets
production unless the operator knows to defeat it, and the two obvious defences both fail:

- `unset DATABASE_URL` does nothing, because the variable was never in the shell — settings reads it
  out of the file.
- `DB_NAME=...` is silently ignored, because `DATABASE_URL` being set means the sqlite branch
  (settings.py:119) is never reached.

Discovered 2026-08-16 the expensive way: a coordinator verifying Wave 1 ran `manage.py migrate` and a
seed script believing both were pointed at a scratch sqlite file. Both ran against production Neon.
Nothing was destroyed — the migration was additive (one nullable column) and the accidental rows were
removed with the owner's approval — but the same mistake with a destructive command would not have
been recoverable.

The working incantation is unobvious: `DATABASE_URL= DB_NAME=<path> uv run manage.py …`, because an
empty string is still "set" as far as `os.environ.setdefault` is concerned but falsy at
`if DATABASE_URL:`.

The hermetic test suite is unaffected — `config/settings_test.py` overrides `DATABASES` explicitly.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Running a `manage.py` command locally cannot reach production by default — it either uses a local database or refuses to start
- [x] #2 Reaching production requires an explicit, deliberate opt-in (an env var or flag whose name says so), not merely the absence of a defence
- [x] #3 The recommended local workflow is written down where someone will find it before running a migration, not only in this task
- [x] #4 The existing deploy path (container start, CI) is unaffected and still reads DATABASE_URL as today
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Cheapest option that satisfies #1 and #2: stop loading the root `.env` for local `manage.py` runs, or
gate the production URL behind a distinctly-named variable (e.g. keep `DATABASE_URL` for the
container and require `DACHAPPLY_ALLOW_PROD_DB=1` before settings will accept a non-local host).
A refuse-loudly check ("DATABASE_URL points at a remote host and DACHAPPLY_ALLOW_PROD_DB is unset")
is a few lines in settings.py and fails closed.

Worth considering alongside: a guard on destructive management commands, since the failure mode here
was not the config but that nothing objected to `migrate` against a production host from a laptop.

CLOSED 2026-08-16. Design chosen: gate on *where the value came from* (a persisted `.env` file vs
the real process environment), not on DEBUG or on parsing the host for "looks local". `load_env_file`
now returns the set of keys it actually populated (i.e. keys not already present before any of this
module's own file loads), and `local_db_guard_blocks(database_url, file_sourced_keys, allow_prod_db)`
in `backend/config/settings.py` raises `ImproperlyConfigured` when `DATABASE_URL` is truthy, came
from a file, and `DACHAPPLY_ALLOW_PROD_DB` is not truthy. Rejected alternative: parsing the URL host
and blocking "non-local" hosts — rejected because it needs URL parsing to get right, and because a
file-sourced value is a strictly better danger signal than host shape (a Neon URL a developer
deliberately typed into their own shell for one command is not the incident that happened here; a
Neon URL that showed up silently from a checked-out `.env` file is). Verified both premises this
design leans on: the container image and CI never carry a `.env` file (`.gitignore` and
`.dockerignore` both exclude it, and `Dockerfile` only `COPY`s `backend/` and the built frontend), so
`DATABASE_URL` there is always a real env var, never file-sourced.

BUG FOUND AND FIXED while verifying AC1: a naive "is this key already in `os.environ`" check is
defeated by Django itself. `LazySettings` retries importing `config.settings` on every failed
attribute access, and CPython drops a module that raised from `sys.modules`, so a guard-raised
exception makes the module re-execute from scratch on the very next settings access within the same
process — but `os.environ` is a real process global and is NOT rolled back between those attempts.
The first (correctly guard-raised) import already wrote `DATABASE_URL` into `os.environ` via
`setdefault`; the retry then saw it as "already there" and stopped treating it as file-sourced,
raising the guard on the retry's very own condition. Measured before the fix: `manage.py check`
against the real repo-root `.env` crashed with `AppRegistryNotReady: Apps aren't loaded yet` — a
Django-internals symptom of the first (swallowed-by-Django) raise skipping `django.setup()`, while a
naive re-check thought a config that would have configured `DATABASES` against production. Fixed with
`_process_env_keys`, a snapshot of `os.environ.keys()` taken once and persisted via a marker
(`_DACHAPPLY_PROCESS_ENV_KEYS`) that itself survives retries the same way, so every retry sees the one
true "before this module touched anything" snapshot rather than its own prior side effects.
Regression test: `test_load_env_file_is_immune_to_its_own_earlier_os_environ_writes` in
`backend/jobradar/tests/test_local_db_guard.py`.

Measured, not reasoned about:
- AC1 (default refuses): `cd backend && uv run manage.py check` against the real repo-root `.env`
  (unmodified, holds the production Neon URL) raised
  `ImproperlyConfigured: DATABASE_URL came from a .env file, ...`. Same result for
  `manage.py showmigrations`. Neither command queried anything — the process never got far enough to
  open a connection.
- AC2 (explicit opt-in): `DACHAPPLY_ALLOW_PROD_DB=1 uv run manage.py check` against the same `.env`
  passed ("System check identified no issues").
- Fail-closed: `DACHAPPLY_ALLOW_PROD_DB=` (empty), `=nope`, and `=0` against the same `.env` all still
  raised the refusal. Covered for the full env_bool truthy/falsy matrix by
  `test_guard_fails_closed_on_garbage_opt_in_value` / `test_guard_opens_on_recognized_truthy_opt_in_values`.
- AC4 (deploy path unaffected): reproduced the container's shape twice — once with the real repo-root
  `.env` still on disk but `DATABASE_URL` exported in the shell first (so it wins via `setdefault`),
  and once in a fully isolated copy of `backend/` with **no `.env` file anywhere in the tree** (the
  container's actual shape, per `.dockerignore`/`Dockerfile`) and `DATABASE_URL` set as a real env
  var. Both: `manage.py check` passed, and `manage.py shell -c "print(settings.DATABASES['default'])"`
  showed `DATABASES` resolved to exactly the injected env var (host/name/user), never the `.env`
  file's value. CI is unaffected trivially — it never sets `DATABASE_URL` at all;
  `config/settings_test.py` blanks it before import regardless.
- AC3 (workflow documented): added a "Before running `migrate`..." callout in `README.md` directly
  above the `manage.py migrate` command in "Local setup and run instructions" — where AC3 required it
  to be, not only here. Also annotated `.env.example`, `.env.local.example`, `.env.local-neon.example`
  and `.env.local-one-server.example` at their `DATABASE_URL` lines with the same opt-in requirement,
  since `.env.local-neon.example` and `.env.local-one-server.example` are existing documented
  workflows that deliberately put a remote `DATABASE_URL` in `.env` and now need the opt-in too.

Full backend suite: `cd backend && uv run pytest -q` — 271 passed (261 pre-existing + 10 new in
`test_local_db_guard.py`), 0 failed. `uv run manage.py check --deploy` (with the opt-in, since the
default refuses before reaching deploy checks) showed the same 6 pre-existing DEBUG=True warnings
(HSTS/SSL-redirect/SECRET_KEY/cookie-security/DEBUG) that are unrelated to this change and not new.

Not implemented, flagged rather than silently dropped: the "guard on destructive management
commands" idea above. The file-sourced-DATABASE_URL guard closes the actual root cause (the value
being reachable at all), so a laptop cannot reach production by default regardless of which command
is run — a separate confirmation prompt on `migrate`/`flush` would be defense-in-depth on top of
this, not required to satisfy any AC here. Worth a follow-up task if the owner wants a second layer.
<!-- SECTION:NOTES:END -->
