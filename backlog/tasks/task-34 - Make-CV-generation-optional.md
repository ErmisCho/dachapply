---
id: TASK-34
title: Make CV generation optional
status: Done
assignee:
  - '@pi'
created_date: '2026-07-16 11:19'
updated_date: '2026-07-16 11:35'
labels:
  - frontend
  - backend
  - ai
dependencies:
  - TASK-31
modified_files:
  - backend/jobradar/services/cv_generator.py
  - backend/jobradar/services/cv_tasks.py
  - backend/jobradar/views.py
  - backend/jobradar/tests/test_api.py
  - frontend/src/App.tsx
priority: medium
ordinal: 34000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Single and batch application generation allow CV-only, letter-only, or both. Generation is blocked when neither document is selected.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 CV and letter both default to selected
- [x] #2 Users can generate a letter without a CV
- [x] #3 Users can generate a CV without a letter
- [x] #4 Generate remains disabled when neither document is selected
- [x] #5 Prompts, schema, compilation, persistence, progress, and archives contain only selected documents
- [x] #6 Tests cover letter-only and invalid empty selection
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Carry one create_cv boolean through the existing endpoint/task/generator and make the current conditional document pipeline symmetric.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Added create_cv symmetrically across single/batch UI, API validation, async task configuration, revision metadata, model schema/prompt, compilation, persistence, progress, and ZIP packaging. Both documents default on; each batch row can independently disable CV or letter; requests with neither are blocked. Letter-only output persists under C:\latex\output and opens that folder. Full validation passed: 111 backend tests, frontend production build, Django check, and whitespace check.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Application generation now supports CV-only, letter-only, or both, while requiring at least one selected document.
<!-- SECTION:FINAL_SUMMARY:END -->
