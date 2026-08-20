---
id: TASK-148
title: Reword TASK-140 AC6 — the spot-check scales with what actually matched
status: To Do
assignee: []
labels:
  - process
  - mailbox
dependencies:
  - TASK-140
priority: low
ordinal: 148000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
TASK-140 AC6 asks to "list the messages newly attached to at least three jobs and confirm by
reading sender and subject that each really is that company's mail." The premise was that the
display-name rule would recover many of the unmatched confirmations. Measured 2026-08-19 against
the real mailbox, the correct, conservative rule attaches exactly ONE message (PIDSO -> job 36):
every other unmatched ATS message names a company that was never tracked, and AC3 forbids
inventing matches for them. Three jobs' worth of newly attached mail therefore cannot exist
without violating AC3 — the criterion is unsatisfiable as worded, and TW-005 says such a
criterion is reworded through its own filed task, never silently relaxed.

The spot-check's intent was fully honoured: 100% of newly attached mail (1 of 1) was read and
confirmed by sender and subject.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 TASK-140 AC6 is reworded to: "Spot-check the result rather than trusting the count: list
      ALL newly attached messages — across at least three jobs when that many gained mail — and
      confirm by reading sender and subject that each really is that company's mail"
- [x] #2 With that wording, the 2026-08-19 measurement (1 of 1 attached messages read and
      confirmed as PIDSO's mail to job 36) satisfies it, and TASK-140 AC6 is ticked citing this task
<!-- AC:END -->
