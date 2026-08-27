---
id: TASK-196
title: Edit notes from every job stage
status: Done
assignee:
  - '@pi'
created_date: '2026-08-27 15:22'
updated_date: '2026-08-27 17:24'
labels:
  - frontend
  - notes
dependencies: []
priority: medium
ordinal: 196000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Let users edit notes they added to a job from the job detail page regardless of whether the job is new, active, rejected, withdrawn, skipped, or archived. The backend already exposes owner-scoped PATCH /api/notes/{id}/; the missing capability is the job-detail UI.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Every user-created general note on a job detail page has an Edit action
- [x] #2 Editing and saving updates the existing note through the owner-scoped note endpoint instead of creating a duplicate
- [x] #3 Cancelling an edit leaves the original note unchanged
- [x] #4 Editing remains available for terminal job statuses, including rejected, withdrawn, skipped, and archived
- [x] #5 Frontend regression coverage proves save, cancel, and terminal-status behavior
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Add status-independent inline editing for general notes in JobNotes.
2. Save through PATCH /api/notes/{id}/ and replace the existing row in local state; cancel restores the stored text without a request.
3. Add focused frontend regression coverage for the Edit control, PATCH/no-duplicate behavior, cancellation, and terminal statuses.
4. Run the frontend test suite and production build, then finalize TASK-196.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented inline editing in the existing JobNotes flow. General notes now expose Edit, Save changes, and Cancel controls. Save reuses the existing owner-scoped PATCH /api/notes/{id}/ endpoint and replaces the matching note in local state, so it does not create duplicates. The editability rule deliberately ignores job status and covers all 11 statuses. No backend or CSS changes were needed.

Validation: frontend npm test — 6 files, 182 tests passed; frontend npm run build — TypeScript and Vite production build passed.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Added status-independent inline editing for general notes on job detail pages, using the existing owner-scoped PATCH endpoint with cancel-safe local state. Added focused regression coverage for Edit visibility, PATCH/no-duplicate behavior, cancellation, and terminal statuses. Verified 182 frontend tests and the production build.
<!-- SECTION:FINAL_SUMMARY:END -->
