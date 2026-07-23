---
id: TASK-33
title: Allow restoring archived jobs
status: Done
assignee:
  - '@pi'
created_date: '2026-07-16 11:13'
updated_date: '2026-07-16 11:14'
labels:
  - backend
  - bug
dependencies: []
modified_files:
  - backend/jobradar/views.py
  - backend/jobradar/tests/test_api.py
priority: high
ordinal: 33000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Archived jobs visible through the archived dashboard filter currently return 404 on PATCH because the ViewSet's default list filter also hides archived detail routes.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Authenticated owners can PATCH an archived job back to new
- [x] #2 Archived jobs remain hidden from the default unfiltered list
- [x] #3 Unauthorized users still cannot update archived jobs
- [x] #4 Regression tests pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Apply the archived exclusion only to list requests; keep ownership filtering on every action.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Root cause: JobLeadViewSet.get_queryset excluded archived rows whenever no status query parameter was present, including PATCH detail lookup. Restricted that default exclusion to list actions only; ownership filtering still applies to every route. Restored TÜV job #440 to new and cleared stale status/interview dates. Three focused tests and Django check passed.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Archived jobs can now be restored through PATCH without becoming visible in the default list or weakening ownership checks. TÜV job #440 is restored to new.
<!-- SECTION:FINAL_SUMMARY:END -->
