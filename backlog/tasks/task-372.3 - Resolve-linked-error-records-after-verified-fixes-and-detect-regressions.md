---
id: TASK-372.3
title: Resolve linked error records after verified fixes and detect regressions
status: Done
assignee: []
created_date: '2026-11-11 15:26'
updated_date: '2026-11-12 17:27'
labels:
  - observability
  - backlog
  - reliability
dependencies:
  - TASK-372.2
parent_task_id: TASK-372
priority: high
type: feature
ordinal: 375000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Implement the resolution part of TASK-372. Done means a bug fix is verified under the existing task-completion policy, not merely that an agent said it was fixed. Mark only the linked occurrence records resolved, retain their history, and exclude them from future error analysis. Preserve detection of genuinely new failures after the fix.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Verified completion of a linked Backlog bug records its fix/verification reference and marks the associated occurrence IDs resolved/done without deleting the evidence or unrelated occurrences.
- [x] #2 A subsequent triage run, application restart and replay/rotation of the same old source records perform zero new analysis or task creation for those resolved occurrence IDs.
- [x] #3 New occurrences are never swallowed by a blanket resolved-signature filter; distinguish replayed historical evidence, an unfixed old runtime/build, and a new post-fix regression using available version/time boundaries.
- [x] #4 A genuine post-fix recurrence produces a new linked regression incident/task or explicitly reopens the matching bug, according to one documented policy; it does not repeatedly reopen on each replay.
- [x] #5 Concurrent error arrival during closure cannot mark later unrelated/new occurrences done, and failed task-status synchronization is retryable without duplicate records or lost evidence.
- [x] #6 An end-to-end lifecycle test covers failure -> grouped task -> verified fix/Done -> linked logs resolved -> old records skipped -> new regression captured, including interrupted synchronization.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Persist verified closure references and atomically resolve only linked occurrence IDs. 2. Route later evidence to stable successor incidents with explicit build uncertainty. 3. Add hermetic lifecycle/retry tests, document policy, run required checks and record results without changing status or AC.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
TASK-372.3 implementation (uncommitted; status and AC unchanged):
- Added additive local error_resolutions history containing linked task/signature, family, fixed build digest, UTC closure boundary and fix/tests/evaluation/merge references.
- Added resolve() and triage_errors --resolve with required completion-reference flags. A trusted maintainer attests passing required tests, PERFECT evaluation and squash merge; Backlog JSON must independently report the linked bug as Done. External reports/merges are not independently fetched or verified. Done alone never resolves evidence.
- Closure and status lookup run in one SQLite write transaction; only already-linked occurrence IDs are resolved, preserving all rows/context/links. Failed sync rolls back; retry and repeated closure are idempotent; concurrent/unlinked intake remains unresolved.
- New evidence gets deterministic successor incidents rather than reopening closed tasks. Fixed-build post-closure evidence is a regression; pre-closure evidence and different/unknown builds are explicitly uncertain. Existing unresolved links remain on their incident. Stable source IDs skip historical replay/rotation after restart. Documented the policy and its collection-time/unknown-build limitations in docs/error-occurrences.md.

AC evidence (all in backend/jobradar/tests/test_error_triage.py):
1: test_resolution_lifecycle_interrupted_sync_and_regression asserts Done gate, retained references/evidence/links and exact linked-ID closure; test_resolved_replay_has_no_analysis_and_command_requires_references checks required references through the command.
2: test_resolved_replay_has_no_analysis_and_command_requires_references asserts restart/replay produces no proposals or CLI calls; lifecycle test replays historical evidence while later incidents remain visible.
3: lifecycle test distinguishes pre-closure unlinked evidence, fixed-build post-closure regression and new old-runtime evidence; stable ID replay stays resolved.
4: lifecycle test checks a separate successor task and zero repeated CLI calls on replay; test_regression_create_interruption_recovers_one_successor checks recovery after external creation succeeds but its response is interrupted.
5: test_resolution_serializes_concurrent_arrival verifies racing intake remains unresolved; lifecycle test verifies failed status lookup leaves evidence unresolved and succeeds on retry without duplicate closure.
6: test_resolution_lifecycle_interrupted_sync_and_regression covers failure -> grouped bug -> verified Done references -> linked resolution -> restart/old replay -> new linked regression, including interrupted status synchronization.

Verification environment: UV_CACHE_DIR was redirected to system temp and PYTHONDONTWRITEBYTECODE=1. Direct uv run pytest initially hit uv cache ACL denial; after redirect, pytest reported 37 setup errors from Windows mode-0700 temp ACLs. A unique --basetemp alone had the same ACL problem. The following in-process pytest launcher changes only test-run os.mkdir(mode=0700) to mode=0777 to avoid that restricted-token ACL failure; no product code/settings were changed for this workaround. All temporary test output stays in system temp.
Common PowerShell setup for each successful launch:
$env:UV_CACHE_DIR = Join-Path $env:TEMP 'task-372-3-uv'
$env:PYTHONDONTWRITEBYTECODE='1'
$env:TASK372_TEMP = Join-Path $env:TEMP ('task-372-3-focused-' + [guid]::NewGuid())
cd backend
Exact focused command (final run: 39 passed, 0 failed; earlier two-test version: 37 passed):
uv run python -c "import os,pytest; original=os.mkdir; os.mkdir=lambda path,mode=0o777,**kw: original(path,0o777 if mode==0o700 else mode,**kw); raise SystemExit(pytest.main(['-q','--tb=line','-p','no:cacheprovider','--basetemp='+os.environ['TASK372_TEMP'],'jobradar/tests/test_error_triage.py','jobradar/tests/test_error_occurrences.py']))"
Full suite was run once, with TASK372_TEMP prefix task-372-3-full-:
uv run python -c "import os,pytest; original=os.mkdir; os.mkdir=lambda path,mode=0o777,**kw: original(path,0o777 if mode==0o700 else mode,**kw); raise SystemExit(pytest.main(['-q','--tb=line','-p','no:cacheprovider','--basetemp='+os.environ['TASK372_TEMP']]))"
Result: 2186 passed, 1 failed, 969 warnings in 825.76 seconds. Failure: jobradar/tests/test_analysis_time_limit.py::test_the_fit_analysis_kills_a_model_process_that_outlives_the_limit; Python sleep(20) child did not exit within model.wait(timeout=5). This cancellation path was not changed; occurrence collection is disabled by default in settings_test.
Isolated confirmation, with TASK372_TEMP prefix task-372-3-cancellation-:
uv run python -c "import os,pytest; original=os.mkdir; os.mkdir=lambda path,mode=0o777,**kw: original(path,0o777 if mode==0o700 else mode,**kw); raise SystemExit(pytest.main(['-q','--tb=line','-p','no:cacheprovider','--basetemp='+os.environ['TASK372_TEMP'],'jobradar/tests/test_analysis_time_limit.py::test_the_fit_analysis_kills_a_model_process_that_outlives_the_limit']))"
Result: 0 passed, 1 failed in 8.15 seconds, same TimeoutExpired. Left unrelated cancellation code unchanged.
Frontend exact commands: cd frontend; npx tsc --noEmit; if ($LASTEXITCODE -eq 0) { npm test }; then separately cd frontend; npm test (npm_config_cache redirected to system temp for the latter). Typecheck exited 1: ENOTCACHED, no installed/cached compiler. npm test exited 1: vitest not recognized. Zero frontend tests executed; no dependencies were downloaded.
git diff --check passed (only Git line-ending notices).
Evaluation: FAILURE, not PERFECT: required full-suite and frontend validation gates are not green. Self-evaluation used a late rubric in system temp, not an independent grader. AC-focused behavior is covered by 39 passing tests; a green full run and frontend checks remain outstanding. No commit/push/merge performed, as explicitly prohibited. No status or AC changes.
2026-11-13 (coordinator): 40 tests incl. end-to-end lifecycle with interrupted sync; review fix: successor keyed on the closure in effect when the error happened (PR 406).
<!-- SECTION:NOTES:END -->
