---
id: TASK-375
title: Skip a job from the queue pipeline
status: Done
assignee: []
created_date: '2026-11-13 14:52'
updated_date: '2026-11-13 16:00'
labels: []
dependencies: []
priority: medium
type: feature
ordinal: 377000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The owner can skip a job directly from the Document queue (waiting, running analysis, or blocked), so it stops consuming model time and leaves the pipeline without opening the job.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Every queue row for a job (queued, running analysis, blocked) offers Skip; a running analysis is stopped first.
- [x] #2 A skipped job leaves the queue and the Blocked list, is marked Not applying (same state as the existing skip decision), and no further analysis or documents start for it.
- [x] #3 Skip is reversible from the job page; un-skipping does not auto-start work.
- [x] #4 Tests cover skip for each row state and that no model call starts afterwards; browser-verified on the queue page.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Reuse skipped job status and pipeline stage; stop active work and remove waiting work; use existing job status control to undo. Add queue controls and hermetic coverage.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented job-wide Skip in the queue using existing skipped job status and skipped pipeline stage. Signals analysis stop events, cancels/removes pending documents, protects against late results and later automatic work, and retains finished documents. Existing job-page status control reverses Skip without triggering preparation; explicit Prepare can resume later. AC1-3: test_queue_skip_stops_job_and_undo_starts_nothing (queued/running/blocked/analysis) and test_queue_stops_analysis_and_cancel_survives_restart[skip]. AC4 automated coverage passes; browser check blocked by missing bundled Chromium, installed Chrome spawn EPERM, and no browser connector surfaces. Status and AC boxes intentionally unchanged.

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
