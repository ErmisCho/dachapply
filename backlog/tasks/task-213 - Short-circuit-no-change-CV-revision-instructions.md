---
id: TASK-213
title: Short-circuit no-change CV revision instructions
status: In Progress
assignee:
  - '@pi'
created_date: '2026-09-01 22:23'
updated_date: '2026-09-01 22:29'
labels:
  - backend
  - cv
  - performance
dependencies: []
modified_files:
  - backend/jobradar/services/cv_tasks.py
  - backend/jobradar/views.py
  - backend/jobradar/tests/test_api.py
priority: high
ordinal: 212000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Readjust and compile currently treats every non-empty instruction as a real revision, so an explicit 'No further CV changes required' confirmation launches model generation and compilation for minutes. Return the current generated artifacts immediately for an unambiguous no-change instruction, while preserving real revisions and correction images.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 An instruction whose first statement is exactly 'No further CV changes required' returns the current artifacts without model or compiler invocation
- [ ] #2 The no-change path completes in under 250 milliseconds at the backend boundary
- [ ] #3 Real edit instructions and any correction image continue through the existing revision workflow
- [ ] #4 The no-change result remains owner-scoped and references only that owner's existing job artifacts
- [ ] #5 Focused regressions cover latest-file recovery and in-memory completed-task revision paths
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Recognize only an exact first statement of 'No further CV changes required' as a no-op; correction images always bypass it. 2. Return the existing ready task for in-memory revisions and create an already-ready owner-scoped artifact task for restart-recovered files. 3. Verify sub-250ms timing, zero model/compiler calls, real-edit/image behavior, ownership, full gates, and release.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Root cause: both revision entry points equated every non-empty instruction with a requested mutation and unconditionally started generation. Implemented an exact first-statement no-change marker. Restart-recovered requests now create an already-ready owner-scoped task containing the unchanged TeX/PDF and downloadable archive; in-memory requests reuse the ready parent. Real edits and correction images retain the existing model path. Focused: 3 passed; broader CV/evidence selection: 28 passed. The endpoint regression enforces <250ms with model and compiler calls replaced by failing sentinels.
<!-- SECTION:NOTES:END -->
