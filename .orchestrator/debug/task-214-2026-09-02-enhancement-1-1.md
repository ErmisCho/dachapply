# TASK-214 Backlog hydration warnings

## Failure

During successful TASK-214 creation, Backlog emitted repeated hydration failures for TASK-150 and TASK-189. Each `git show <sha>:backlog/tasks/<long filename>.md` failed with `fatal: failed to stat ... Filename too long` on Windows.

## Root cause

The Backlog history hydrator asks Git for legacy long task paths that exceed the Windows path/stat boundary. TASK-214 itself was still created successfully with exit code 0.

## Resolution

Do not alter legacy task files or the Backlog package during this scoped CV change. Verify TASK-214 directly via `backlog task view`; preserve this warning for the existing housekeeping track.
