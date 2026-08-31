---
id: TASK-208
title: Change lead status from the feedback deadlines pane
status: In Progress
assignee:
  - '@pi'
created_date: '2026-08-31 13:50'
updated_date: '2026-08-31 14:40'
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
- [ ] #1 Every feedback-deadline row offers the existing feedback-date reschedule control and a status selector using the application's real job statuses
- [ ] #2 Changing status updates the owner-scoped job through the existing job update path and refreshes the pane without a full page reload
- [ ] #3 Moving a lead to a non-actionable status removes it from the pane; actionable status changes remain visible with the new status
- [ ] #4 A failed status or date update is reported and does not appear to succeed
- [ ] #5 Synthetic backend/frontend regressions cover reschedule plus status changes without using owner data
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Reuse the existing feedback row, global status vocabulary, and owner-scoped PATCH /jobs/{id}/ path rather than adding an endpoint. 2. Add a per-row Status selector alongside I followed up and Reschedule; send the same status/date/stage defaults the board uses, then reload the feedback pane so terminal statuses disappear and actionable statuses stay current. 3. Surface failed status and date writes in the pane instead of allowing optimistic state to look successful. 4. Add a DOM-less synthetic control test plus an API regression proving status persistence and pane removal. 5. Run full gates, browser-check the interaction, evaluate, merge, verify runtime/deployment, and close.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Reused PATCH /jobs/{id}/ through one small feedback-pane mutation helper shared by reschedule and status. The row now exposes all 11 real statuses. Successful writes refresh board state and the server-sorted pane; failures return the real error without an optimistic success. Terminal statuses disappear via the existing actionable-status filter; actionable changes remain. Verification: 1041 backend tests, 201 frontend tests, production build, Django/migration/compile checks, npm audit, synthetic browser date+status interaction, and fake success/failure PATCH tests passed. Asian Dad self-evaluation: PERFECT.
<!-- SECTION:NOTES:END -->
