---
id: TASK-31
title: Generate CV packages for selected jobs in batch
status: Done
assignee:
  - '@pi'
created_date: '2026-07-16 07:14'
updated_date: '2026-07-16 10:30'
labels:
  - frontend
  - backend
  - ai
dependencies:
  - TASK-30
modified_files:
  - frontend/src/App.tsx
priority: high
ordinal: 31000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The owner can select multiple dashboard jobs and launch CV plus optional-letter generation for every selected job. The batch shows per-job progress, failure, task ID, and download so each output is traceable.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The generation button appears when multiple jobs are selected
- [x] #2 One action starts generation for every selected job using each job's detected language and matching templates
- [x] #3 Letter generation remains enabled by default and can be disabled for the whole batch
- [x] #4 The batch displays per-job progress, errors, task IDs, and downloads
- [x] #5 Focused checks cover the batch workflow
- [x] #6 Batch mode offers shared provider, model, effort, and speed controls
- [x] #7 Each selected job independently offers CV language and letter type or no letter
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Reuse the existing per-job preview, generation, and task-status endpoints from one small batch UI; do not add a second backend orchestration layer.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Added a multi-selection batch generation dialog on the dashboard. It reuses each job's preview and existing asynchronous generation endpoint, defaults letters on, and shows per-job language, progress, stage/error, task ID, and download. No duplicate backend batch layer was added. Validation passed: frontend TypeScript/Vite production build, three focused CV task API tests, and git diff check.

Follow-up: expose the active generation stage and processed/total package count directly in the batch action button.

The running button now displays CV vs. CV + letter, processed/total count, and the active backend stage; the dialog summary separately shows processed and ready counts. Frontend production build and git diff check passed.

Follow-up: restore shared provider/model/effort/speed controls in batch mode and add per-job CV language plus letter type/none controls.

Batch mode now exposes the same shared AI provider/model/effort/speed choices as single generation. Every selected job independently defaults from language detection but allows changing CV language and choosing a matching letter type or No letter. The selected settings are sent through the existing per-job generation endpoint. Frontend production build and git diff check passed.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Multi-job generation now combines shared AI settings with per-job CV language and optional letter-type selection, while retaining live progress and task traceability.
<!-- SECTION:FINAL_SUMMARY:END -->
