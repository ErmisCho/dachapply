---
id: TASK-28
title: Allow readjusting the latest generated application
status: Done
assignee:
  - '@pi'
created_date: '2026-07-15 15:41'
updated_date: '2026-07-16 06:49'
labels:
  - frontend
  - backend
  - ai
dependencies:
  - TASK-27
modified_files:
  - backend/jobradar/services/cv_generator.py
  - backend/jobradar/services/cv_tasks.py
  - backend/jobradar/views.py
  - backend/jobradar/urls.py
  - backend/jobradar/tests/test_api.py
  - frontend/src/App.tsx
priority: medium
ordinal: 28000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
After generation, the owner can provide follow-up instructions to revise the latest CV and optional letter, recompile them, and keep a new version without modifying protected templates.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Generation UI accepts revision instructions for the latest job output
- [x] #2 Revision uses the latest generated TeX plus candidate evidence and original job context
- [x] #3 Revised files compile and are saved as a new collision-safe version
- [x] #4 Protected base templates remain unchanged
- [x] #5 Tests cover revision task creation and versioned outputs
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Retain local task artifact metadata, add a revision endpoint and instructions UI, then reuse asynchronous generation and compilation.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Added owner-only revision instructions after a completed generation. Revisions reuse the latest persisted TeX artifacts and original task configuration/context, run through the same asynchronous model/LaTeX pipeline, and persist collision-safe new files without touching templates. Validation passed: 7 focused backend tests, Django check, and frontend production build. The full API test file reached completion under system Python with 103 passed and one unrelated missing-openpyxl environment failure; the project venv run completed all test progress but did not exit before timeout.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
The latest generated CV and optional letter can now be readjusted, recompiled, downloaded, and saved as a new collision-safe version. Verified with focused backend tests, Django checks, and frontend build.
<!-- SECTION:FINAL_SUMMARY:END -->
