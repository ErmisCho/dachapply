---
id: TASK-22
title: Run local CV generation asynchronously with progress
status: Done
assignee:
  - '@pi'
created_date: '2026-07-15 14:57'
updated_date: '2026-07-15 15:02'
labels:
  - backend
  - frontend
  - ai
dependencies:
  - TASK-21
priority: high
ordinal: 22000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner-only local Codex generation should return immediately, expose honest milestone progress, and download the completed package without blocking the web request. The Generate button fills left-to-right and names the current completed or active stage.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Starting generation returns a task ID without waiting for Codex or LaTeX
- [x] #2 Task status reports queued, generating, generated, compiling CV, CV compiled, compiling letter, and ready or failed milestones
- [x] #3 The Generate button fills left-to-right according to reported progress and displays the current stage
- [x] #4 The completed ZIP downloads automatically and failures remain visible
- [x] #5 Local-only asynchronous state cannot be accessed by another user
- [x] #6 Tests cover progress milestones, asynchronous API authorization, and completion
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Add a single-worker in-memory task queue suitable for the local-only feature. 2. Emit generation and compilation milestones from the existing service. 3. Add status/download endpoints. 4. Poll and render progress in the button. 5. Run focused backend tests and frontend build.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented a single-worker local in-memory queue so Codex/LaTeX no longer block HTTP requests. Added owner-scoped task status and download endpoints, milestone callbacks through generation/compilation, automatic polling/download, and a button fill layer that transitions left-to-right while displaying the active stage. Kept CV and letter in one Codex call to avoid doubling subscription usage. Validation: 105 backend tests passed, frontend production build passed, and Django system check passed. Existing demo scheduler startup traceback remains unrelated.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
CV generation now runs asynchronously locally. The button fills by real milestones, names each generation/compilation stage, downloads automatically when ready, and displays failures.
<!-- SECTION:FINAL_SUMMARY:END -->
