---
id: TASK-37
title: Copy generated TeX to clipboard
status: Done
assignee:
  - '@pi'
created_date: '2026-07-16 11:47'
updated_date: '2026-07-16 14:15'
labels:
  - frontend
  - backend
  - workflow
dependencies:
  - TASK-34
modified_files:
  - backend/jobradar/services/cv_tasks.py
  - backend/jobradar/tests/test_api.py
  - frontend/src/App.tsx
priority: low
ordinal: 37000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
After single-job generation or readjustment completes, the generated CV TeX is copied to the local Windows clipboard; letter TeX is used when no CV was requested. Browser clipboard remains a fallback.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Ready task status exposes the selected generated TeX content only to the owning user
- [x] #2 Single generation automatically attempts to copy CV TeX, or letter TeX for letter-only output
- [x] #3 Every successful readjustment copies the latest TeX version
- [x] #4 The same dialog reports clipboard success or permission failure
- [x] #5 Tests and frontend build pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Read the persisted selected TeX into owner-scoped task metadata, copy it from the local generation worker using the standard-library Windows GUI clipboard, and retain navigator.clipboard plus Copy TeX as fallbacks.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Ready task metadata now includes owner-scoped clipboard_tex read from the persisted CV TeX, or letter TeX for letter-only jobs. Single generation and every readjustment automatically attempt navigator.clipboard.writeText. The same dialog reports success/failure and provides a user-gesture Copy TeX fallback for browser permission restrictions. Two focused backend tests, frontend production build, Django check, and whitespace check passed.

Browser clipboard writes after asynchronous polling can be denied despite localhost. Use the local Windows clipboard from the generation worker first, with browser copy as fallback.

Automatic browser clipboard writes were denied after asynchronous polling. The local generation worker now writes TeX directly to the Windows clipboard via tkinter immediately after persistence; task status reports clipboard_copied so the frontend avoids the denied browser call. Browser automatic/manual copy remains fallback for non-local or clipboard failures. Focused test, frontend build, Django check, and whitespace check passed.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Completed generation and revisions now copy TeX directly to the local Windows clipboard, with browser and manual fallbacks.
<!-- SECTION:FINAL_SUMMARY:END -->
