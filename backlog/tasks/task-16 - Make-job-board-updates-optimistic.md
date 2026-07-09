---
id: TASK-16
title: Make job board updates optimistic
status: Done
assignee:
  - '@assistant'
created_date: '2026-07-09 09:42'
updated_date: '2026-07-09 09:44'
labels: []
dependencies: []
modified_files:
  - frontend/src/App.tsx
ordinal: 16000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Inline edits on the dashboard, especially status changes like new -> applied, currently wait for the API and reload before the row updates. Make the board update immediately in local UI, then persist the PATCH in the background and recover on failure.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Changing a job status updates the visible row immediately before the API reload finishes
- [x] #2 The backend PATCH still persists the change and the row refreshes with server data when it returns
- [x] #3 If the PATCH fails, the UI reports the error and reloads server state
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Add a tiny dashboard helper that merges PATCH data into the local row before awaiting the API.\n2. Route visible inline job updates through that helper; keep server response replacing the optimistic row and reload on failure.\n3. Run frontend build and commit the completed work.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Added a dashboard patchJob helper that merges changes into the local jobs array before awaiting PATCH. Status, bulk status/archive, row edit save, and interview stage edits now update the row immediately; the server response replaces the optimistic row, and failures show the error and reload server state. Validation: cd frontend && npm run build passed.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Dashboard inline job updates are now optimistic: the row changes locally before PATCH finishes, server data replaces it on success, and failures show an error plus reload. Verified frontend build passed.
<!-- SECTION:FINAL_SUMMARY:END -->
