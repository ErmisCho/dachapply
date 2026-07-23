---
id: TASK-38
title: Raise CV generation rate limit for batch and revisions
status: Done
assignee:
  - '@pi'
created_date: '2026-07-16 14:40'
updated_date: '2026-07-16 14:42'
labels:
  - backend
  - bug
  - ai
dependencies: []
modified_files:
  - backend/config/settings.py
  - backend/jobradar/tests/test_api.py
priority: high
ordinal: 38000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The owner-only generation throttle defaults to 3/hour, so normal batches and repeated readjustments return 429 before work can be queued.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Default owner generation limit supports practical batches and repeated revisions
- [x] #2 CV generation remains user-throttled and configurable by environment
- [x] #3 Tests verify requests above the previous three-per-hour ceiling
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Raise the existing configurable default rather than removing throttling.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Raised the default configurable CV generation throttle from 3/hour to 100/hour. The same per-user throttle and RATE_LIMIT_CV_GENERATION_USER override remain. Regression test submits four generation requests successfully, above the old ceiling. Focused test, Django check, and whitespace check passed.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Normal batches and repeated revisions no longer hit the former three-per-hour limit; generation remains configurable and user-throttled at 100/hour by default.
<!-- SECTION:FINAL_SUMMARY:END -->
