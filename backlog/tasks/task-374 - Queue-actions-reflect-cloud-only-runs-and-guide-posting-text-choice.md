---
id: TASK-374
title: Queue actions reflect cloud-only runs and guide posting-text choice
status: In Progress
assignee:
  - '@pi'
created_date: '2026-11-12 08:45'
updated_date: '2026-11-12 09:25'
labels: []
dependencies: []
modified_files:
  - backend/jobradar/tests/test_analysis_lanes.py
  - backend/jobradar/tests/test_application_prep.py
  - frontend/src/prepQueue.test.tsx
  - backend/jobradar/services/application_prep.py
  - frontend/src/PrepQueue.tsx
  - frontend/src/App.tsx
  - backend/jobradar/tests/test_link_only_prep.py
  - docs/verification-2026-11-12-queue-guidance.md
priority: high
type: bug
ordinal: 376000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Fix the reported queue screenshot: cloud retry must not be offered for active cloud-only analyses; text-choice blocks must guide users to the existing explicit chooser without overwriting either text.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Running fit and requirements analyses already using cloud-only mode do not offer cloud retry; local-capable and failed analyses still offer it.
- [ ] #2 A posting-text-choice block offers Choose job text instead of a non-resolving Retry, linking to the existing editor; unrelated blocked states retain their controls.
- [ ] #3 Navigation preserves both texts; Keep current and Use fetched resume through the existing path.
- [ ] #4 Focused regressions fail before the fix and pass afterwards; disposable browser and backend/frontend checks pass without paid model calls or production data changes.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Use the actual active-run cloud mode and pending cloud reruns for availability; expose a text-choice flag; link to the existing job page chooser; verify red/green tests, browser, gates, review and merge.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Execution moved to the user-approved isolated worktree. This record replaces uncommitted TASK-373 in the original checkout; no second fix or scope added. Groma is not initialized, so no architecture reference IDs are available.

Red baseline: 14 backend cases and one frontend regression failed as intended. Initial green: 101 backend / 521 frontend. Visible browser found async CV panel growth shifted the job-text anchor below the viewport; added a focus-guarded resize observer so the chooser stays visible until the user moves focus. Text remains unchanged until an explicit choice.

Full suite found a real poll-query regression: eager account lookup increased idle polls from two to three queries. Corrected to read the fallback mode lazily only for an active unregistered row. Also observed a Windows process-cancellation timing failure; the unchanged test passed in the independent fetch worktree, and a direct owned-process tree-kill check succeeded in 0.85 seconds. No assertion or production cancellation behavior weakened.
<!-- SECTION:NOTES:END -->
