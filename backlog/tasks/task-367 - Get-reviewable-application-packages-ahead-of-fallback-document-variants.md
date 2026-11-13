---
id: TASK-367
title: Get reviewable application packages ahead of fallback document variants
status: Done
assignee: []
created_date: '2026-11-11 15:24'
updated_date: '2026-11-12 14:02'
labels:
  - pipeline
  - performance
dependencies: []
priority: medium
type: enhancement
ordinal: 367000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Grounded opportunity from Backlog doc-1, Application pipeline efficiency opportunities - 2026-11-11. Historical timings are not a controlled speedup comparison. Preserve TASK-348 all-letter alternatives, TASK-303 model quality/defaults, owner data, cancellation, per-account access and daily budgets. The automatic preparation queue appends all variants of one job to a shared FIFO. Extra alternatives can sit ahead of the next job first useful CV/letter package. Improve time to useful packages across jobs without discarding requested alternatives or pretending total model work has disappeared.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A repeatable multi-job workload measures baseline and resulting time to first/next reviewable CV plus required/recommended letter package, as well as total batch completion.
- [ ] #2 Useful packages are not unnecessarily delayed behind other jobs fallback variants; all applicable requested alternatives are still enqueued and eventually produced.
- [x] #3 Owner Move-to-front actions, cancellation/retry, restart recovery, account isolation and daily limits retain their documented behavior.
- [ ] #4 Queue ordering/progress/ETA describe the actual scheduling; a focused regression test demonstrates the changed scheduling rather than only checking metadata.
- [x] #5 Ship a scheduling change only with measured first-package improvement and no missing required documents or lost alternatives; otherwise record the rejected approach and evidence.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Build a hermetic fixed-duration multi-job measurement against the existing FIFO pump. 2. Compare stable useful-document-first scheduling with FIFO, including all template alternatives and batch completion. 3. Keep scheduling code only if AC5 first-package gate passes; otherwise retain the measurement and record rejection. 4. Run focused and full backend tests plus frontend checks; leave status and AC unchanged.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
TASK-367: Built test_package_scheduling.py before any production scheduling edit. main ecf70f5 and starting HEAD a739edd have identical application_prep.py (git diff main -- backend/jobradar/services/application_prep.py was empty). The experiment captures real prepare/_gate variants for three German jobs with required or preferred cover letters, then drives the real _pump using a fixed-duration fake generator (CV 10 s, each letter 20 s), virtual completion events, and temporary artifact files. Candidate is stable partition: CV/recommended letters before non-recommended letter templates. Every run produces all 12 requested documents exactly once; queue positions and per-document/batch ETA are checked against actual simulated finishes. One slot: FIFO package times 30/100/170 s, candidate 30/60/90 s, batch 210 s for both. Two slots: FIFO 20/60/90 s, candidate 20/40/50 s, batch 110 s for both. Both required and preferred cases give identical results. AC5 REJECTED: first-package improvement is 0 s (0%) at both concurrency levels. No production scheduling code is retained; the rejected candidate exists only in the repeatable experiment. This does not claim that every possible scheduling approach fails. AC1 and AC5 have direct measurement evidence; AC2 and changed-scheduling part of AC4 are intentionally not shipped under AC5. AC3 retains existing production behavior because production code is unchanged. No status/AC changes, commits or pushes.

Validation environment: backend/pytest.ini selects config.settings_test (in-memory sqlite). uv run pytest initially failed initializing the default uv cache; retry with a temp cache attempted dependency installation, which was blocked by unavailable network, and created an ignored .venv in this worktree. Automatic approval review rejected removing that created directory with reason 'blocked by policy'; it remains. Used existing parent virtualenv with VIRTUAL_ENV=C:/Users/Administrator/Backup/Projects/dachapply/.venv, UV_CACHE_DIR=C:\Users\Administrator\AppData\Local\Temp/task-367-uv-cache, PYTHONPYCACHEPREFIX=C:\Users\Administrator\AppData\Local\Temp/task-367-pycache, and uv run --active --no-sync. Windows sandbox denies access to pytest directories created with mode 0700; a system-temp-only runner task-367-pytest.py normalizes mode 0700 to 0777 only under the system temp directory, inserts backend cwd into sys.path, and calls pytest.main. All --basetemp values are fresh GUID directories under system temp. No repository harness/config changes. Exact final measurement command from backend: uv run --active --no-sync python (Join-Path C:\Users\Administrator\AppData\Local\Temp 'task-367-pytest.py') -q --tb=line -p no:cacheprovider --basetemp= jobradar/tests/test_package_scheduling.py => 4 passed. Earlier combined focused run of this file plus jobradar/tests/test_application_prep_queue.py jobradar/tests/test_queue_estimate.py jobradar/tests/test_all_letters.py => 64 passed, 4 failed from a missing workspace fixture argument in the new test; that argument is fixed and the final 4 measurement cases pass. Frontend commands from frontend: npx --no-install tsc --noEmit => blocked ENOTCACHED (no local TypeScript, 0 tests); npm test => blocked, vitest not recognized (0 tests). Dependencies were not installed. Full backend suite launched once with the same runner and flags, without file filters; result pending.

Final validation: full backend suite ran once from backend with uv run --active --no-sync python (Join-Path C:\Users\Administrator\AppData\Local\Temp 'task-367-pytest.py') -q --tb=line -p no:cacheprovider --basetemp= (fresh system-temp GUID directory): 2143 passed, 1 failed, 969 warnings in 972.91 s. All new scheduling measurements and existing focused queue/ETA/all-letter cases passed in this full run. The sole failure is jobradar/tests/test_analysis_time_limit.py::test_the_fit_analysis_kills_a_model_process_that_outlives_the_limit at line 120: model.wait(timeout=5) raises subprocess.TimeoutExpired for the fake Python process sleeping 20 s. Isolated reproduction command: uv run --active --no-sync python (Join-Path C:\Users\Administrator\AppData\Local\Temp 'task-367-pytest.py') -q --tb=short -p no:cacheprovider --basetemp= jobradar/tests/test_analysis_time_limit.py::test_the_fit_analysis_kills_a_model_process_that_outlives_the_limit => 1 failed in 7.50 s with the same error, without loading the new measurement module. No changes made to the unrelated timeout behavior. git diff --check passes. AC3 evidence includes existing Move-to-front, cancel, retry, resume and owner-access tests in test_application_prep_queue.py plus daily-limit tests in test_auto_pipeline.py, all passing in the full suite. AC4 experiment checks actual pump start order and finish-time ETA, but no production scheduling change is shipped because AC5 rejects this candidate. AC/status remain unchanged. Frontend checks remain blocked by absent dependencies. The temporary ignored worktree .venv remains after automatic approval review rejected its cleanup; all later caches, runner, artifacts and pytest basetemp output were directed to system temp.
2026-11-13 (coordinator): measurement showed no first-package improvement (30s/20s unchanged), so per AC5 no scheduling change shipped; AC2/AC4 describe a shipped change and do not apply. Rejected approach + numbers in notes above (PR 402).
<!-- SECTION:NOTES:END -->
