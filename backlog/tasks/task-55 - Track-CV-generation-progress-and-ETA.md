---
id: TASK-55
title: Track CV generation progress and ETA
status: Done
assignee:
  - '@pi'
created_date: '2026-08-06 15:35'
updated_date: '2026-08-12 16:56'
labels: []
dependencies: []
modified_files:
  - backend/jobradar/services/cv_tasks.py
  - backend/jobradar/views.py
  - backend/jobradar/tests/test_api.py
  - frontend/src/App.tsx
priority: high
ordinal: 56000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Make CV generation visibly fill its Generate/Generating controls from left to right using live backend task progress, while continuously showing an honest time estimate for single-job, batch, and readjustment flows.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Single-job Generate and readjust controls fill left to right, show the current stage and percentage, and show an ETA throughout active work
- [x] #2 Batch generation shows per-job and aggregate progress with ETAs on the active Generate control
- [x] #3 Progress is anchored to real backend generation/compile/save checkpoints, advances between checkpoints from measured or conservative stage timing, and reaches 100% only when ready
- [x] #4 Queued jobs include queue time in their ETA and failed/ready jobs stop estimating
- [x] #5 Focused backend tests and the frontend production build pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Add server-side stage timing, interpolation, and queue-aware ETA fields to CV task status. 2. Return initial task estimates from start endpoints. 3. Reuse a minimal progress-button presentation for single, readjustment, and batch generation. 4. Add focused tests and run backend/frontend checks.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented server-owned live progress with monotonic stage timing, conservative first-run estimates that learn matching stage durations in-process, and single-worker queue-aware ETAs. The single, readjustment, batch-row, and aggregate Generate controls now fill left-to-right and show stage, percentage, and remaining time. Validation: 4 focused backend tests passed with --reuse-db; frontend production build passed; Python compilation and diff checks passed. A full backend run progressed through 61 tests but exceeded the 300-second command limit; a subsequent non-reuse run was blocked by the still-active PostgreSQL test database session.

Follow-up validation: full backend suite passed with the project virtualenv (127 tests in 238.85s; one existing PostgreSQL teardown warning), frontend production build passed, and makemigrations --check reported no changes.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Added live, queue-aware CV generation progress and ETA reporting plus filling progress buttons for single, readjustment, and batch flows. Progress remains anchored to actual generation/compile/save checkpoints and reaches 100% only on ready; focused backend coverage and the frontend production build pass.
<!-- SECTION:FINAL_SUMMARY:END -->
