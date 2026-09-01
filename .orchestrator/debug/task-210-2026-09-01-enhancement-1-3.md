# TASK-210 browser-fixture migration failure

## Failure

A disposable SQLite migration failed with `django.db.utils.OperationalError: unable to open database file`.

## Root cause

The requested isolated database path was `.orchestrator/runtime/task210-browser.sqlite3`, but this worktree did not contain the ignored `.orchestrator/runtime/` parent directory. SQLite creates the file but not missing parent directories.

## Resolution

Create the disposable parent directory and rerun the unchanged migration. This is verifier setup only; no product change is indicated.
