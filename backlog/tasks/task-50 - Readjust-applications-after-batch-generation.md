---
id: TASK-50
title: Readjust applications after batch generation
status: Done
assignee: []
created_date: '2026-07-24 10:26'
updated_date: '2026-07-24 10:29'
labels: []
dependencies:
  - TASK-28
  - TASK-31
modified_files:
  - frontend/src/App.tsx
ordinal: 51000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
After generating CVs and motivation letters for multiple selected jobs, users need the same follow-up optimization workflow available for a single job, without leaving the batch dialog.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Each batch job provides revision instructions for its latest generated CV and/or letter
- [x] #2 Readjusting one batch job reuses that job's selected document types and shared model settings
- [x] #3 Per-job revision progress, errors, report, and download update independently
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Add per-job revision state and an existing revise-latest API call to the batch dialog.
2. Show compact revision controls and reuse current per-row polling, reports, errors, and downloads.
3. Run focused backend endpoint checks, build the frontend, and restart the app.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Added an Adjust latest generated files section to every batch row. Each row independently sends its instructions, selected CV/letter types, and shared provider/model/effort/speed to the existing persisted revise-latest endpoint. Existing row polling now carries the revised task ID, progress, errors, report, and download; successful revisions clear only that row's instructions. No duplicate backend batch revision layer was added.

Validation: frontend production build passed; 3 focused revision/generation API tests passed; full backend suite passed (124 tests) on local SQLite; whitespace check passed. Restarted localhost and verified the served bundle contains both single and batch revise-latest calls; health is 200/database ok.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Batch-generated applications can now be optimized per job inside the batch dialog using the same persisted revision workflow as single-job generation.
<!-- SECTION:FINAL_SUMMARY:END -->
