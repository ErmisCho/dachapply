---
id: TASK-15
title: Hide unanalyzed jobs from main board
status: Done
assignee:
  - '@assistant'
created_date: '2026-07-09 09:36'
updated_date: '2026-07-09 09:39'
labels: []
dependencies: []
modified_files:
  - backend/jobradar/views.py
  - backend/jobradar/tests/test_api.py
  - frontend/src/App.tsx
ordinal: 15000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The main dashboard job board should not show job listings that have no analysis/evaluation yet. Saved but unanalyzed jobs should still exist for prompt generation/import workflows, but they should not appear as regular board rows until analyzed.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The main board excludes jobs with no latest evaluation by default
- [x] #2 Unanalyzed jobs remain accessible for existing prompt/import workflows and counts
- [x] #3 A regression check covers the filtered board behavior
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Inspect how the dashboard fetches jobs and how unanalyzed counts/prompts use the API.\n2. Add the smallest backend filter so the main board excludes no-evaluation jobs while opt-in flows can still fetch them.\n3. Add one API regression test and run the relevant checks.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Added an optional analyzed=1 jobs API filter and made the dashboard board request use it. Existing prompt/analyze flows keep using the unfiltered jobs endpoint, so unanalyzed saved jobs remain available for analysis. Added API regression coverage. Validation: backend pytest 95 passed; frontend npm run build passed.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Dashboard job board now requests only analyzed jobs via analyzed=1, while prompt/analyze workflows still fetch unfiltered jobs so new unanalyzed links can be analyzed. Added backend regression coverage. Verified backend pytest 95 passed and frontend build passed.
<!-- SECTION:FINAL_SUMMARY:END -->
