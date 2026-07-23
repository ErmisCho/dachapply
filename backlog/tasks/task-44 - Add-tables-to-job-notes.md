---
id: TASK-44
title: Add tables to job notes
status: Done
assignee: []
created_date: '2026-07-23 14:07'
updated_date: '2026-07-23 14:54'
labels: []
dependencies: []
modified_files:
  - frontend/src/App.tsx
ordinal: 45000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Job detail notes should support normal text followed by one or more persistent tables, and saved notes should display with the same structure.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A job note can contain text followed by a table
- [x] #2 The note editor can add multiple tables before saving
- [x] #3 Saved notes reload and display their text and tables in order
- [x] #4 Existing plain-text notes remain readable
- [x] #5 Pasted ChatGPT Markdown tables render as visible tables, including tables without outer pipe characters
- [x] #6 The dashboard Notes popup displays saved Markdown tables as rendered tables instead of raw pipe text
- [x] #7 The dashboard Notes popup expands horizontally for wide multi-column tables
- [x] #8 Saving dashboard notes keeps the Notes popup open
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Keep the dashboard note modal state after create, update, or delete; update its note ID from the API response and show a saved confirmation.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented the note table editor and renderer using Markdown stored in the existing note field, preserving existing plain-text notes and avoiding schema/dependency changes. Validation: frontend npm run build passed; backend pytest passed (118 tests, 1 existing teardown warning); git diff --check passed.

Follow-up: pasted ChatGPT table Markdown could remain literal text because table detection required every row to start with an outer pipe.

Fixed table detection for ChatGPT Markdown with or without leading/trailing pipes, ignored Markdown code fences, and added a live formatted preview before save. Frontend build and git diff check passed.

Screenshot identified the actual affected interface: the dashboard quick-notes modal, not the job detail Notes section fixed earlier.

Updated the dashboard quick-notes modal shown in the screenshot: existing notes now open in rendered view, Edit notes reveals the textarea plus a rendered preview, and the modal scrolls for wide/long tables. Confirmed the stored EBCONT note is valid Markdown table content. Frontend build and git diff check passed.

Expanded the dashboard quick-notes modal from max-w-lg to max-w-6xl so four-column and wider tables use available desktop width. Frontend build and diff check passed; restarted localhost server and verified the new asset returns 200.

Save notes now updates or creates the note in place, preserves the open modal and editing state, updates the returned note ID, and shows a Notes saved confirmation. Frontend build/diff check passed; localhost restarted and new asset verified with HTTP 200.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Dashboard notes support rendered wide tables and now save without closing the popup, with an inline saved confirmation.
<!-- SECTION:FINAL_SUMMARY:END -->
