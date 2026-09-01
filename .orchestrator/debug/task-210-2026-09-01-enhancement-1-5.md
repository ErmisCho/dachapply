# TASK-210 browser login wait timeout

## Failure

After submitting the inspected login form, the verifier timed out waiting 10 seconds for the dashboard.

## Root cause

The visible form showed the generic server error, and the isolated backend log showed `sqlite3.OperationalError: no such table: dachapply_cache` from login throttling. Django migrations do not create the configured database-cache table; disposable local databases need the separate built-in `createcachetable` command.

## Resolution

Run `manage.py createcachetable` against the disposable database and retry login. This is verifier setup only; no application change is warranted.
