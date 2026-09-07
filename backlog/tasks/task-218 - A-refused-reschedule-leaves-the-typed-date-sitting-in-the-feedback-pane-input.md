---
id: TASK-218
title: A refused reschedule leaves the typed date sitting in the feedback-pane input
status: Done
assignee: []
created_date: '2026-09-07 13:57'
updated_date: '2026-09-07 16:03'
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

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Closed 2026-09-07 in commit 38d46e7 (PR #132), deployed and production-verified.

onReschedule widened to Promise<boolean> so the row sees the outcome applyFeedbackDueWrite already computed; the blur handler restores row.feedback_due_date on a refused write, guarded by el.value===v so a slow refusal cannot overwrite a date typed since. defaultValue kept deliberately - FeedbackDueRow/FeedbackDueList are called as plain functions by the suite, so a hook would have broken three existing tests, and an empty keystroke path means nothing can fight segment entry.

Measured in the running app with the PATCH intercepted and never forwarded:
- refused: input 2026-10-15 -> 2026-09-08 (the server value), error shown, server unchanged
- accepted with the pane refetch echoing the save: input reads 2026-11-20, no error, no reload
Job 462 read interview / 2026-09-08 before and after.

Falsification: restoring the old handler reds 'puts the stored date back in the input when the write is refused' with expected '2026-10-15' to be '2026-09-08'; sha256 identical after revert.

NOT verified as written: rubric criterion 4 asked for live partial date entry. Real keystrokes do not reach inputs in the automated tab - a control probe typing into the board search box left it empty, so an early date-field observation proved nothing. Established structurally instead: the rendered input carries no value, onChange, onInput, onKeyDown or onKeyUp, so no code runs during segment entry. Re-confirmed on the owner's localhost after merge.

Gates: 220 frontend tests (was 216), tsc clean, build index-OnOhPdoS.js, backend untouched. Deploy from 38d46e7 succeeded; /api/health/ returns {status:ok, database:ok}. Owner runtime fast-forwarded; localhost re-verified - 2 rows, 11 statuses, displayed date matches the server, no stray errors, no false empty-state claim.

Asian Dad: PERFECT, all 7 sealed criteria PASS (self-graded disclosure stands).

Known gap, not an AC: if a write succeeds but the server normalises the date, the input keeps the typed value until reload. Closing it needs onReschedule to return the saved date, not a boolean.
<!-- SECTION:NOTES:END -->
