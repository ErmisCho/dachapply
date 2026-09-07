---
id: TASK-218
title: A refused reschedule leaves the typed date sitting in the feedback-pane input
status: In Progress
assignee: []
created_date: '2026-09-07 13:57'
updated_date: '2026-09-07 15:51'
labels:
  - frontend
  - board
  - feedback
dependencies: []
priority: low
ordinal: 217000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The feedback-deadline row's date control is uncontrolled (defaultValue={row.feedback_due_date} in frontend/src/App.tsx), and the row's key does not change across a failed write, so no remount occurs. After a refused reschedule the input keeps displaying the date the owner typed, which was never saved. Measured live on 2026-09-07 by intercepting the PATCH and answering 500: the error alert appeared and the server value stayed 2026-09-08, but the input still read 2026-10-15 until a page reload. The pane as a whole is truthful (the error is shown and the Due badge keeps the old deadline), so this did not fail TASK-208's criterion that failures must not appear successful - but the control itself is displaying an unpersisted value and should not. Predates TASK-208; the reschedule control was not introduced by it.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 After a refused reschedule the date input shows the value still stored on the server
- [x] #2 A successful reschedule still shows the newly saved date without a reload
- [x] #3 A synthetic frontend regression fails if the input goes back to keeping the unsaved value
<!-- AC:END -->
