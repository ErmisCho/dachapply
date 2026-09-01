# TASK-212 released timing verifier settings failure

## Failure

The first released timing measurement launched `manage.py shell` without clearing the `.env` production `DATABASE_URL`; the intentional fail-closed settings guard raised `ImproperlyConfigured` before importing the model-discovery module.

## Root cause

The timing probe needs Django setup but no database. It omitted the repository's explicit `DATABASE_URL=` opt-out for read-independent management commands.

## Resolution

Retry unchanged with `DATABASE_URL=` so Django uses local SQLite configuration; the probe itself still performs no database, model, or network call. Preserve this artifact in the closure PR.
