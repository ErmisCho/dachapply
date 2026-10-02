---
id: TASK-258
title: Data import that sets a job to Applied should clean its generated metadata
status: Done
assignee: []
created_date: '2026-10-01 20:43'
updated_date: '2026-10-01 21:26'
labels:
  - backend
  - workflow
dependencies: []
priority: low
ordinal: 256000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Follow-up to TASK-256. user_data_portability import can update an existing job's status to applied (JOB_FIELDS includes status) without going through JobLeadSerializer, so TASK-256's Applied cleanup (delete_generated_metadata, read-only sent-document link) never runs for it.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 An import that changes an existing job from a non-applied status to applied runs the same cleanup as the board PATCH: working sidecar removed, sent-document read-only link kept
- [x] #2 Cleanup runs only after the import's transaction commits; a rolled-back or failed import leaves metadata untouched
- [x] #3 An import that leaves a job's status unchanged, sets a non-applied status, or creates a new job does not delete any metadata
- [x] #4 A cleanup error never fails the import or changes what it persisted
- [x] #5 Regression tests cover each case above and fail when the import hook is removed
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Hook: `import_user_export` in `backend/jobradar/services/user_data_portability.py`, existing-job branch. The status is captured before `_assign_fields`; when the record changed and the status went from non-applied to `applied`, it registers `transaction.on_commit(lambda job=obj: delete_generated_metadata(job), robust=True)` — the same function and pattern as `JobLeadSerializer.update` (TASK-256). The create branch has no hook.

Transaction finding: the whole import loop already runs inside `with transaction.atomic():`, so on_commit defers until that block commits (or to the outermost transaction when nested). `ATOMIC_REQUESTS` is not set anywhere in `config/`. It does not fire immediately.

A lambda, not `functools.partial`: Django 5.2's robust on_commit error handler logs `callback.__qualname__`, which a partial lacks, so a raising partial would crash the handler meant to swallow the error. The default argument binds the current job, since `obj` is reassigned on the next loop iteration.

Tests: `backend/jobradar/tests/test_import_applied_cleanup.py` (7 cases). Each was checked against a mutant of the hook:
- hook removed: fails `..._cleans_metadata_after_commit`, `test_rolled_back_import_leaves_metadata_untouched`, `test_cleanup_error_never_fails_the_import`.
- cleanup run immediately rather than on commit: the same 3 fail.
- transition guard removed (cleanup on any existing-job update): all 3 `test_import_without_applied_transition_keeps_metadata` cases fail.
- hook also added to the create branch: `test_import_creating_an_applied_job_runs_no_cleanup` fails.
- `robust=True` dropped: `test_cleanup_error_never_fails_the_import` fails.
The negative tests (AC3) pass when the hook is simply removed — absence of cleanup is their claim — so they are proven by the guard/create-branch mutants instead.

Full backend suite: `1256 passed, 522 warnings in 592.80s`.

Not done here: commit, PR, merge, production verification (coordinator).

Coordinator 2026-10-01: merged as #201 (d4c5731), deploy green, production /api/health/ 200. Coordinator re-ran the 7 tests (pass) and removed the hook (3 fail).
<!-- SECTION:NOTES:END -->
