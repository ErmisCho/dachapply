---
id: TASK-376
title: Cancel a queued job and restart it later
status: Done
assignee: []
created_date: '2026-11-13 14:53'
updated_date: '2026-11-13 16:00'
labels: []
dependencies: []
priority: medium
type: feature
ordinal: 378000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The owner can cancel a job's pipeline or document work in the queue and restart it later, even after it was cancelled, without losing the job's posting text, requirements or already finished documents.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Running analyses and running/queued documents offer Cancel; cancellation stops the model call and shows the row under Failed/cancelled.
- [x] #2 A cancelled job or document offers Restart at any later time (also after a server restart) and resumes from the step that was cancelled, reusing finished results.
- [x] #3 Restart re-checks the daily limits and the job's current state (e.g. a changed posting) before starting.
- [x] #4 Tests cover cancel and later restart for analysis and document rows, including after a restart of the server; browser-verified on the queue page.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Persist cancelled analysis stage and resume step; reuse document cancellation; add explicit Restart with current-state and budget checks. Verify focused and full suites and browser queue controls.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented persistent cancelled analysis stage with resume_stage and explicit Restart, plus Restart labels for cancelled documents. Restart rechecks account daily budgets, current job status, pending source choices, document posting snapshot and existing preparation gates. Finished sibling documents, posting text and requirements remain intact. Late worker completion cannot undo cancellation. AC1-2: test_cancelled_document_restart_after_server_restart and test_queue_stops_analysis_and_cancel_survives_restart[cancel]. AC3: test_document_restart_rechecks_state_and_limit and test_cancelled_requirements_restart_reuses_fit_and_checks_budget. AC4 automated coverage passes; browser verification blocked by missing bundled Chromium, installed Chrome spawn EPERM, and no browser connector surfaces. Status and AC boxes intentionally unchanged.

Validation (Windows sandbox): npx tsc --noEmit (frontend): PASS, 0 errors. npm test -- --configLoader native --cache=false --pool=threads (frontend): 522 passed, 0 failed, 45 files. Plain npm test startup was blocked by spawn EPERM; native config loading and threads ran the same suite without changing configuration.
Focused backend: 101 passed, 0 failed. Exact shell invocation from backend: set $env:UV_CACHE_DIR=Join-Path $env:TEMP 'task375-uv-cache', then pipe this stdin to uv run python -:
```python
import os
original_mkdir=os.mkdir
def mkdir(path,mode=0o777,*,dir_fd=None):
    return original_mkdir(path,0o777,dir_fd=dir_fd)
os.mkdir=mkdir
import pytest
raise SystemExit(pytest.main(['-q','--tb=line','-p','no:cacheprovider','--basetemp',os.path.join(os.environ['TEMP'],'task375-focused-final'),'jobradar/tests/test_application_prep_queue.py','jobradar/tests/test_analysis_lanes.py','jobradar/tests/test_skip_leaves_blocked.py']))
```
The temporary mkdir mode compatibility wrapper avoids WinError 5 from Python 3.13's mode-0700 temp directories in this sandbox; no project settings or test logic changed. The requested direct uv run pytest -q --tb=line -p no:cacheprovider jobradar/tests/test_application_prep_queue.py jobradar/tests/test_analysis_lanes.py initially produced 58 setup errors from temporary-directory permissions (no assertion failures). All tests use config.settings_test and in-memory sqlite. Full suite result follows below.

Final review: retained the re-analysis reason in pipeline stage metadata so Restart does not treat an unchanged stale recheck as a changed posting and redo finished documents. Added a guard against restarting a cancelled document while its old worker is still stopping. Repeated focused suite with basetemp task375-focused-final-2: 101 passed, 0 failed. Same uv run python - bootstrap, pytest arguments ['-q','--tb=line','-p','no:cacheprovider','--basetemp',os.path.join(os.environ['TEMP'],'task375-worker-stop-final'),'jobradar/tests/test_application_prep_queue.py::test_document_restart_waits_for_cancelled_worker']: 1 passed, 0 failed. The earlier full run was interrupted at 41% with no reported failures to include these final review fixes; the complete final-state run follows.

Final full backend suite (final code): 2243 passed, 1 failed, 977 warnings in 807.24s. Exact invocation from backend: the same os.mkdir compatibility stdin bootstrap documented above, piped to uv run python -, ending with:
```python
raise SystemExit(pytest.main(['-q','--tb=line','-p','no:cacheprovider','--basetemp',os.path.join(os.environ['TEMP'],'task375-full-final-2')]))
```
Failure: jobradar/tests/test_analysis_time_limit.py::test_the_fit_analysis_kills_a_model_process_that_outlives_the_limit, subprocess.TimeoutExpired waiting five seconds for the child model process. Isolated rerun with pytest arguments ['-q','--tb=short','-p','no:cacheprovider','--basetemp',os.path.join(os.environ['TEMP'],'task375-process-stop-check'),'jobradar/tests/test_analysis_time_limit.py::test_the_fit_analysis_kills_a_model_process_that_outlives_the_limit']: 0 passed, 1 failed.
Baseline verification: loaded git show HEAD:backend/jobradar/services/application_prep.py into the existing module namespace in memory (no checkout or file replacement), then ran the same isolated test with basetemp task375-baseline-process-stop: 0 passed, 1 failed with the same timeout. A separate disposable-child probe confirmed taskkill /PID <own-child-pid> /T /F returns code 1 and ERROR: Access denied in this sandbox. Existing process-control code was not changed.
Final automated counts: focused 101 passed plus separately added worker-stop test 1 passed; frontend 522 passed; TypeScript 0 errors. Browser AC remains unverified (Chrome launch spawn EPERM; no browser connector available). No PERFECT completion signoff claimed because browser verification and a fully passing full suite are blocked by the environment. No commit, push, status change, or AC checkbox changes performed.
2026-11-13 (coordinator): red/green checked (9 backend + 2 frontend new tests fail on main); full backend suite 2244 passed; browser smoke `queue Skip, Cancel and Restart` green 3x incl. coordinator rerun (skip leaves every region with no further model call; cancel/restart analysis; cancel/restart letter without regenerating the CV).
<!-- SECTION:NOTES:END -->
