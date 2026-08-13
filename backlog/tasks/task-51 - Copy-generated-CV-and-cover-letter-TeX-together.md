---
id: TASK-51
title: Copy generated CV and cover-letter TeX together
status: Done
assignee: []
created_date: '2026-07-24 10:41'
updated_date: '2026-07-24 10:45'
labels: []
dependencies:
  - TASK-37
  - TASK-50
modified_files:
  - backend/jobradar/services/cv_tasks.py
  - backend/jobradar/tests/test_api.py
  - frontend/src/App.tsx
ordinal: 52000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
When both a CV and cover letter are generated, the clipboard currently receives only the CV TeX. Users need both TeX files combined in one clipboard payload for ChatGPT, automatically and through manual copy buttons in single and batch generation.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A completed CV-plus-letter task automatically copies both TeX contents with clear file separators
- [x] #2 Single-job generation provides a button to copy both generated TeX files
- [x] #3 Each batch row provides a button to copy that job's generated TeX files
- [x] #4 CV-only and letter-only generation still copy the available TeX
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Combine every generated TeX artifact into the existing owner-scoped clipboard payload.
2. Keep automatic worker copy and expose manual copy feedback in single and batch rows.
3. Extend the task regression test, build, run checks, and restart the app.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
The generation worker now builds one owner-scoped clipboard payload from every existing generated TeX artifact. When both files exist, it includes CV then cover letter with filename comment separators; single-file output remains unchanged. Automatic local Windows clipboard copy uses this combined payload.

Single and batch UIs now both expose Copy generated TeX files buttons. Batch rows report automatic copy success and keep independent manual copy errors/messages. Because one clipboard has one current value, batch completion leaves the most recently completed job's CV+letter pair there; each row button copies that specific job's pair again.

Validation: combined/CV-only/letter-only regression assertions pass; 2 focused owner/task tests passed; full backend suite passed (124 tests) on local SQLite; frontend build and whitespace check passed. Restarted localhost, verified both copy buttons in the served bundle, and health is 200/database ok.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
CV and cover-letter TeX are now copied together automatically with clear separators, with manual copy buttons in both single and batch workflows.
<!-- SECTION:FINAL_SUMMARY:END -->
