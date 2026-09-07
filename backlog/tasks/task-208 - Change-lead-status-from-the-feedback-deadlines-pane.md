---
id: TASK-208
title: Change lead status from the feedback deadlines pane
status: Done
assignee:
  - '@pi'
created_date: '2026-08-31 13:50'
updated_date: '2026-09-07 14:13'
labels:
  - frontend
  - board
  - feedback
dependencies: []
modified_files:
  - frontend/src/App.tsx
  - frontend/src/feedbackDueControls.test.tsx
  - backend/jobradar/tests/test_api.py
  - .orchestrator/debug/task-208-2026-08-31-enhancement-1-1.md
  - .orchestrator/debug/task-208-2026-08-31-enhancement-1-2.md
  - .claude/.asian-dad/task-208-feedback-status-rubric.json
  - >-
    backlog/tasks/task-208 -
    Change-lead-status-from-the-feedback-deadlines-pane.md
priority: high
type: enhancement
ordinal: 207000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Each lead in the Feedback deadlines pane already supports recording a follow-up and changing the feedback date. Add an owner-scoped status control on the same row so the lead can be rescheduled and/or moved to its correct job status without navigating away, while preserving the existing date and audit behavior.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Every feedback-deadline row offers the existing feedback-date reschedule control and a status selector using the application's real job statuses
- [x] #2 Changing status updates the owner-scoped job through the existing job update path and refreshes the pane without a full page reload
- [x] #3 Moving a lead to a non-actionable status removes it from the pane; actionable status changes remain visible with the new status
- [x] #4 A failed status or date update is reported and does not appear to succeed
- [x] #5 Synthetic backend/frontend regressions cover reschedule plus status changes without using owner data
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Reuse the existing feedback row, global status vocabulary, and owner-scoped PATCH /jobs/{id}/ path rather than adding an endpoint. 2. Add a per-row Status selector alongside I followed up and Reschedule; send the same status/date/stage defaults the board uses, then reload the feedback pane so terminal statuses disappear and actionable statuses stay current. 3. Surface failed status and date writes in the pane instead of allowing optimistic state to look successful. 4. Add a DOM-less synthetic control test plus an API regression proving status persistence and pane removal. 5. Run full gates, browser-check the interaction, evaluate, merge, verify runtime/deployment, and close.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
AC5 closed 2026-09-07 in commit ee67920 (PR #129). The task had been merged with all five criteria unchecked and a self-graded PERFECT; independent verification found AC1-AC4 true and AC5 false.

The gap: Dashboard is unexported, so changeFeedbackStatus, rescheduleFeedback, loadFeedbackDuePanel and feedbackDueActionErr appeared in no test. All 7 frontend and 6 backend tests stayed green with the row wiring no-oped, status_date or interview_stage dropped from the payload, the pane refresh deleted, or the error box deleted. Each is now observed RED and reverted.

Fix: extracted feedbackStatusPatch and applyFeedbackDueWrite (collaborators as parameters, matching the existing updateFeedbackDueJob idiom) and lifted FeedbackDueList/FeedbackDuePaneHeader out of renderDashboardPanel. Behaviour unchanged. Backend gained the reschedule PATCH test, which had zero coverage - the old test only proved the date survives a status patch, true even if the field had gone read-only.

The outermost prop hand-off is still beyond the suite, so it was measured in Chrome against the running app with the PATCH intercepted and never forwarded: correct lead, correct body, refusal shows the server message and reverts the select with no refetch, success refetches exactly once. Job 462 read interview / 2026-09-08 before and after.

Gates: 1055 backend, 212 frontend, tsc clean, build index-DA30aGee.js. Deploy from ee67920 succeeded; /api/health/ returns {status:ok, database:ok}; owner localhost re-verified rendering the pane (2 rows, 11 statuses, reschedule input, no stray errors). The authenticated board was NOT observed in production - it is behind a login and no credentials were entered.

Asian Dad: PERFECT, all 6 sealed criteria PASS (self-graded disclosure stands). Filed TASK-217 and TASK-218 for two pre-existing defects found during verification.
<!-- SECTION:NOTES:END -->
