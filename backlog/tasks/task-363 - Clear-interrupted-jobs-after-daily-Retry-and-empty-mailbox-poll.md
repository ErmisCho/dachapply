---
id: TASK-363
title: Clear interrupted jobs after daily Retry and empty mailbox poll
status: In Progress
assignee:
  - '@implementation-agent'
created_date: '2026-11-06 07:25'
updated_date: '2026-11-06 07:42'
labels: []
dependencies: []
modified_files:
  - backend/jobradar/tests/test_processing_counts.py
  - backend/jobradar/services/processing_control.py
  - backend/jobradar/services/application_prep.py
  - backend/jobradar/tests/runtime_retry_fixture.py
  - backend/jobradar/tests/test_processing_retry_lifecycle.py
priority: low
ordinal: 363000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
TEMP-93 follow-up to PR 367. Isolated data only; do not deploy or touch the live runtime.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A successful retry after interrupted inline daily analysis clears the wrapper interruption without resolving other jobs or owners.
- [x] #2 A successful empty scheduled mailbox poll clears a matching interruption without counting idle polls as completed jobs.
- [x] #3 Regressions fail on main and pass with the fix, including a real isolated process kill and Retry lifecycle.
- [x] #4 Backend pytest and frontend clean install/build pass; deliver a separate PR against main.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Reproduce both accounting bugs. 2. Repair wrapper handoff and empty poll completion identity. 3. Exercise isolated kill/Retry and run the project gate. 4. Review and push a focused PR.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-09: renumbered from TASK-348, which the cover-letter task (#370) also used; code comments citing TASK-348 mean that one. Code done (#369); Done waits for a production deploy and check (TW-00A).

Both new count regressions failed on unchanged main (daily 3 vs 2; empty poll 2 vs 1), then 26 queue/count tests passed. Isolated runtime kill/HTTP Retry reached ready and zero interruptions; corrected expected completed count to include requirements analysis.

Full gate passed: uv run pytest -q (1912 passed in 722.61s); npm ci and npm run build passed. Real disposable dashboard process killed during inline daily analysis; after startup HTTP Retry reached one ready document, two completed jobs (analysis + document), and zero interrupted/pending/running jobs. Other-owner/job and failed/skipped mailbox cases covered. Groma is not initialized, so no architecture references were invented. No live service changes or deployment.

PR: https://github.com/ErmisCho/dachapply/pull/369. Evaluation is self-graded against the pre-implementation rubric; no independent reviewer was dispatched. Frontend install reported 5 dependency advisories (3 moderate, 2 high) and the build emitted its large-chunk warning; dependencies and frontend source were not changed.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Fixed both interruption counters; 1912 backend tests and frontend npm ci/build pass. Added red/green regressions plus real isolated runtime kill and HTTP Retry. Delivered PR #369 against main. Backlog remains In Progress pending merge per repository policy; Multica implementation issue is delivered per owner handover rule.
<!-- SECTION:FINAL_SUMMARY:END -->
