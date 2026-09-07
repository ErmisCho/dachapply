---
id: TASK-217
title: 'A failed feedback-pane refresh reads as an empty pane, not an error'
status: In Progress
assignee: []
created_date: '2026-09-07 13:47'
updated_date: '2026-09-07 15:35'
labels:
  - frontend
  - board
  - feedback
  - silent-failure
dependencies: []
priority: medium
ordinal: 216000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
loadFeedbackDuePanel() in frontend/src/App.tsx ends with catch{setFeedbackDueRows([])}. When the post-write GET /api/jobs/feedback-due/ fails, the pane empties and renders 'No actionable job has a feedback deadline right now.' with no error shown. Immediately after a status change that is indistinguishable from the lead having been correctly filtered out, so the owner reads a network failure as a successful status move. Found during TASK-208 verification on 2026-09-07; predates TASK-208 (introduced with TASK-146) and is outside its ACs, which scope to a failed status or date write rather than a failed refresh.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A failed feedback-due refresh surfaces an error instead of an empty pane
- [x] #2 The empty-state sentence is shown only when the server actually returned zero rows
- [x] #3 A synthetic frontend regression fails if the catch is restored to silently emptying the rows
<!-- AC:END -->
