---
id: TASK-196
title: Edit notes from every job stage
status: Done
assignee:
  - '@pi'
created_date: '2026-08-27 15:22'
updated_date: '2026-08-28 06:54'
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

Completion-policy correction: implementation is committed, pushed, fully tested, and Asian Dad verdict is PERFECT. Task remains In Progress until its implementation branch is squash-merged into main; a post-merge completion change will set Done.

Final post-rebase validation: backend 992 passed; frontend 182 passed; production build passed. Existing TASK-196 Asian Dad verdict remains PERFECT.

Squash-merged PR #86 into main as f95bdcf2c16641cf739e090ae944c0edae4342f2 after GitHub test and GitGuardian checks passed.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Added status-independent inline editing for general job notes using the owner-scoped PATCH endpoint with cancel-safe, no-duplicate local replacement. Verified 992 backend tests, 182 frontend tests, production build, Asian Dad PERFECT, and squash merge via PR #86 (f95bdcf).
<!-- SECTION:FINAL_SUMMARY:END -->
