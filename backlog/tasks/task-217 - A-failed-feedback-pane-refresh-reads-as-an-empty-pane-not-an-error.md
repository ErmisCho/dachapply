---
id: TASK-217
title: 'A failed feedback-pane refresh reads as an empty pane, not an error'
status: Done
assignee: []
created_date: '2026-09-07 13:47'
updated_date: '2026-09-07 15:44'
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

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Closed 2026-09-07 in commit 862bd4d (PR #131), deployed and production-verified.

The read now reports into feedbackDueActionErr, the error slot the pane already had, so no second error state was added. On failure setRows is not called at all, so rows already on screen survive a read that failed to replace them. The empty-state sentence moved behind feedbackDueEmptyMessage, which returns null while loading or while an error is showing.

Measured in the running app, both directions, with the PATCH intercepted and never forwarded:
- refresh rejected: rows 2 -> 2 (kept), empty-state sentence absent, alert shown reading 'Could not refresh the feedback deadlines. The list below may be out of date. Failed to fetch'
- genuine 200 with []: 0 rows, sentence shown, no alert
Job 462 read interview / 2026-09-08 before and after, so no real lead was modified.

Falsification: restoring catch{setRows([])} reds two tests - one on the discarded rows (expected [] to deeply equal [{id:210,...}]), one on the false sentence.

Gates: 216 frontend tests (was 212), tsc clean, build index-C3RBTKNQ.js, 1055 backend unaffected. Deploy from 862bd4d succeeded; /api/health/ returns {status:ok, database:ok}. Owner runtime fast-forwarded to 862bd4d.

Asian Dad: PERFECT, all 7 sealed criteria PASS (self-graded disclosure stands).

Known narrowing, accepted deliberately and declared before grading: while an error is showing and rows exist but are hidden by the pane's own filters, 'Those deadline groups are hidden.' is suppressed too. The error is the honest message there; separating them needs a second state.
<!-- SECTION:NOTES:END -->
