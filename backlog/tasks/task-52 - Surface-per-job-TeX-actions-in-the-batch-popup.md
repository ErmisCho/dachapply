---
id: TASK-52
title: Surface per-job TeX actions in the batch popup
status: Done
assignee: []
created_date: '2026-07-24 10:57'
updated_date: '2026-07-24 10:58'
labels: []
dependencies:
  - TASK-50
  - TASK-51
modified_files:
  - frontend/src/App.tsx
ordinal: 53000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Per-job optimization and TeX copy controls exist inside a collapsed section. Make the copy action and automatic-copy status directly visible on each analyzed job row in the multiple-selection popup, while keeping revision instructions scoped to that row.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Each ready batch row shows its own Copy generated TeX files button next to Download
- [x] #2 Automatic copy feedback is visible on the corresponding job row
- [x] #3 Revision instructions remain independently scoped to each job row
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Move each row's copy button beside its Download action.
2. Show that row's automatic/manual clipboard feedback without opening revision controls.
3. Build and restart the app.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Moved Copy generated TeX files from the collapsed optimizer section to each ready job row, directly beside Download. Automatic/manual clipboard feedback now appears on that same row. The per-job Adjust latest generated files section remains independently scoped below it.

Validation: frontend production build and whitespace check passed. Restarted localhost, verified the served bundle contains the per-job copy action and automatic feedback, and health is 200/database ok.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Every analyzed job in the multiple-selection popup now exposes its own visible download, combined-TeX copy, feedback, and independent optimization controls.
<!-- SECTION:FINAL_SUMMARY:END -->
