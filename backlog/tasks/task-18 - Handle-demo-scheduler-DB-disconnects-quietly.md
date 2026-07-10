---
id: TASK-18
title: Handle demo scheduler DB disconnects quietly
status: Done
assignee:
  - '@assistant'
created_date: '2026-07-09 11:37'
updated_date: '2026-07-09 11:39'
labels:
  - bug
  - backend
dependencies: []
modified_files:
  - backend/jobradar/services/demo_scheduler.py
  - backend/jobradar/tests/test_api.py
ordinal: 18000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The background demo seed scheduler can hit stale Neon SSL/DNS failures during local runserver and prints a full traceback even though demo seeding is optional.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Scheduler closes stale DB connections around background DB work
- [x] #2 Transient database errors from claiming the demo seed task log a warning instead of a traceback
- [x] #3 Regression test covers database claim failure
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Use Django close_old_connections in the scheduler thread before/after background DB work.\n2. Log database claim failures as a one-line warning because demo seeding is optional.\n3. Add a small regression test for claim DatabaseError.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Added close_old_connections around the scheduler loop and before claim work. Demo seed database claim failures now log a warning without traceback. Added regression test for DatabaseError during task claim. Validation: backend pytest 97 passed.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Demo scheduler now closes old DB connections around background work and logs optional seed claim DB failures as warnings instead of tracebacks. Verified with backend pytest: 97 passed.
<!-- SECTION:FINAL_SUMMARY:END -->
