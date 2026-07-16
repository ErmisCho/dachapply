---
id: TASK-26
title: Make motivation letter optional in generation
status: Done
assignee:
  - '@pi'
created_date: '2026-07-15 15:41'
updated_date: '2026-07-15 15:49'
labels:
  - frontend
  - backend
  - ai
dependencies:
  - TASK-25
priority: medium
ordinal: 26000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The generation panel defaults to creating a compatible motivation/application letter with the CV, but the owner can choose CV only.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Create letter defaults to enabled
- [x] #2 User can disable letter generation before starting
- [x] #3 CV-only generation skips letter model output, compilation, progress stages, and files
- [x] #4 Tests cover default and CV-only flows
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Add a create-letter control, carry it through tasks, and make prompt/schema/compilation conditional.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Added a Create motivation letter checkbox defaulting on. CV-only tasks use a CV-only schema/prompt, skip letter source/output/compilation/progress, and package one PDF. The UI hides the letter selector and changes the panel title when disabled. Seven focused tests and frontend build passed.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Users can now generate only a CV or retain the default CV plus compatible letter flow.
<!-- SECTION:FINAL_SUMMARY:END -->
