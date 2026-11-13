---
id: TASK-377
title: One blocked or stalled job never holds up the rest of the queue
status: Done
assignee: []
created_date: '2026-11-13 15:35'
updated_date: '2026-11-13 17:43'
labels: []
dependencies: []
priority: high
type: bug
ordinal: 379000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner request 2026-11-13: if one job in the queue is blocked, the others continue. Blocked jobs (waiting for the owner) already stay out of the run queue; this task proves that with a regression test and removes the remaining single-job stalls, e.g. a hung analysis occupying the only analysis slot until the 5-minute limit. An account-wide provider usage limit may still pause all work, and the queue says so.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Regression test: with one job blocked (text choice, missing posting, failed analysis), other jobs' analyses and documents start and finish.
- [x] #2 A stalled analysis is freed by the existing analysis time limit (5 min). Early stall detection was measured and rejected by the owner on 2026-11-13: a normal 76 s model call produced no output for 64 s, so any shorter inactivity limit would stop healthy analyses.
- [x] #3 When an account-wide usage limit pauses everything, the queue states that it is a provider limit affecting all jobs and when it resumes.
- [x] #4 Existing ordering, Move to front, cancel/skip (TASK-375/376) and time-limit behaviour stay green; browser-verified with one blocked job and others progressing.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Add analysis inactivity detection using stage changes and observed model output; retain the global deadline and cancellation guards. 2. Expose an aggregate provider pause and render one queue notice, with regressions. 3. Run focused backend, full backend once, frontend typecheck and tests; record evidence without changing status or ACs.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Part 2 implementation (2026-11-13; changes deliberately uncommitted):
- Added ANALYSIS_STALL_SECONDS (environment configurable, default 45 seconds). The shared bounded analysis worker tracks inactivity separately from the unchanged profile time limit, observes stage transitions and model output, sets the existing stop event on a stall, releases its lane, and records a visible failed analysis with owner Retry/Restart. It does not automatically retry stalled runs.
- Captured CLI stdout/stderr use temporary streams during watched analyses so byte growth is observable on Windows too (Windows communicate() does not expose partial output). Local HTTP response bytes notify the same per-analysis observer across the socket thread. Temporary output stays under system temp.
- Persisted usage-limit identity separately from transient retry metadata. queue_state emits one top-level paused object (provider_limit + resume_at) while provider-limit retries are waiting and no work is running/queued; expired waits do not show a pause. PrepQueue renders one provider-limit notice stating that it affects all jobs and the local resume date/time.
- Removed the strict xfail from the measured lane-release regression. Added actual captured-output progress, local-response byte observation without network, and aggregate provider-pause/expiry/non-provider coverage; added the frontend single-notice regression.

AC evidence:
1. test_blocked_job_does_not_hold_other_analyses_or_documents: all three blocked reasons (source choice, missing posting, failed analysis) pass; other jobs analyse and finish documents.
2. test_stalled_analysis_releases_the_only_lane_before_the_time_limit passes: a .1-second inactivity threshold releases the only lane and starts the next job within .25 seconds, against an independently scaled 1-second global time limit; the abandoned run's stop hook is true and its state says Analysis failed / Analysis stalled. test_slow_analysis_with_model_output_keeps_its_lane passes across twelve .03-second output intervals with a .12-second inactivity threshold. test_local_model_bytes_are_observed_without_network passes.
3. test_provider_limit_pause_is_aggregated_and_expires passes, including ordinary retry exclusion. Frontend test 'shows one provider limit notice with the resume time for all jobs' passes.
4. Ordering, Move to front, Skip/Cancel/Restart and the other time-limit tests pass in the focused and full selections. The existing process-tree-kill test fails in this Windows sandbox; independent reproduction launching a harmless 3-second child and running taskkill /PID <pid> /T /F returned exit 1, ERROR: Access denied. No browser verification was performed: validation here used hermetic backend tests and rendered frontend tests; no disposable browser scenario was established. AC4 is not claimed complete.

Commands and counts:
- Requested direct backend command, uv run pytest -q --tb=line -p no:cacheprovider <focused files>: initially blocked by uv cache access; UV_CACHE_DIR under system temp avoids that. Pytest then reports 83 setup errors because Python 3.13's mode-0700 temp directories cannot be read by this Windows runner. A fresh --basetemp alone has the same issue.
- Runnable test-process adaptation (no repository test/config change): set UV_CACHE_DIR to %TEMP%/task377-uv-cache; run uv run python -c "import os,pytest; mkdir=os.mkdir; os.mkdir=lambda path,mode=0o777,**kw: mkdir(path,0o777 if mode==0o700 else mode,**kw); raise SystemExit(pytest.main([...]))". This uses inherited directory permissions for test-created directories only. All basetemp paths and logs are in system temp.
- Latest focused pytest.main arguments: ['-q','--tb=line','-p','no:cacheprovider','--basetemp='+os.path.join(os.environ['TEMP'],'task377-final-focus'),'jobradar/tests/test_queue_isolation.py','jobradar/tests/test_analysis_lanes.py','jobradar/tests/test_analysis_time_limit.py','jobradar/tests/test_application_prep_queue.py']. Result: 82 passed, 1 failed (the existing process-kill test), 54 warnings, 55.29s. An earlier wider focused run including test_processing_cancellation_lifecycle.py had 80 passed, 3 failed: two SQLite concurrency failures that did not recur in the latest focused or full run, plus the same process-kill failure.
- Full backend suite run exactly once, after implementation: same adaptation; pytest.main(['-q','--tb=line','-p','no:cacheprovider','--basetemp='+os.path.join(os.environ['TEMP'],'task377-full-inherited')]). Result: 2251 passed, 1 failed (test_the_fit_analysis_kills_a_model_process_that_outlives_the_limit), 984 warnings, 779.04s. Log: %TEMP%/task377-full-backend.log.
- cd frontend; npx tsc --noEmit: PASS, no type errors.
- cd frontend; npm test: cannot start the default config/process pool (spawn EPERM). Runnable equivalent: npm test -- --configLoader native --no-cache --pool threads --maxWorkers 2: 45 test files passed, 523 tests passed, 0 failed. Native config and disabled cache avoid generated config/cache output in the repository.
- git diff --check: PASS. No commit, push, reset, stash, checkout, production database, paid model/provider calls, CI/auth/secrets edits, status changes or AC checks.

Acceptance audit: NOT PERFECT because the required backend suites retain the reproduced Windows process-kill failure and browser verification is outstanding. No claim that AC4 or overall completion is verified.
2026-11-13 (coordinator): Codex built an output-based stall detector (45 s). A real probe (gpt-6.1-sol high via the CLI) ran 76 s with only 6 progress events and a 64 s silent gap, so the detector would have stopped normal analyses. Owner chose to drop it and keep the 5-minute limit; detector code and its tests removed. Shipped: blocked-job isolation tests (PR 413) and the account-wide provider-limit pause notice. Verified: queue/lane/isolation tests 74 passed, prepQueue tests 33 passed, tsc clean; full suite and smoke run in CI.
<!-- SECTION:NOTES:END -->
