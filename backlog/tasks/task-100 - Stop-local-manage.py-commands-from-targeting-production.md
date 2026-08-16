---
id: TASK-100
title: Stop local manage.py commands from targeting production
status: To Do
assignee: []
created_date: '2026-08-16 12:10'
labels:
  - backend
  - safety
  - dx
dependencies: []
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
- [ ] #1 Running a `manage.py` command locally cannot reach production by default — it either uses a local database or refuses to start
- [ ] #2 Reaching production requires an explicit, deliberate opt-in (an env var or flag whose name says so), not merely the absence of a defence
- [ ] #3 The recommended local workflow is written down where someone will find it before running a migration, not only in this task
- [ ] #4 The existing deploy path (container start, CI) is unaffected and still reads DATABASE_URL as today
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
<!-- SECTION:NOTES:END -->
