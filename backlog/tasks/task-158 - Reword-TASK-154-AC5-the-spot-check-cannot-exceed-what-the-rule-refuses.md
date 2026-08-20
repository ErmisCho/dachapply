---
id: TASK-158
title: Reword TASK-154 AC5 — the spot-check cannot exceed what the rule refuses
status: Done
assignee: []
labels:
  - process
  - mailbox
dependencies:
  - TASK-154
priority: low
ordinal: 158000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
TASK-154 AC5 asks for "a spot-check of at least three of them confirming each really is bulk".
Measured 2026-08-20 against the real mailbox immediately after the guard shipped, exactly **one**
stored message qualifies, so three cannot be produced without either loosening the rule (which would
be the bug this task existed to prevent) or inventing examples.

The measurement, over every message matched to a job the owner still acts on:

    actionable matched messages     58
    would be refused a suggestion    1

and that one is `Digitl GmbH <noreply@join.com>` on job 599, subject "Generative AI Engineer (all
Genders) for Vienna" — a job-ad blast from JOIN's unattended sender, refused for
"unattended sender address (no-reply)". The same message was refused by the live `check_mailbox`
run (as message 1008), which printed "1 suggestion(s) refused as bulk mail".

A second, honest limitation belongs in the record: stored rows carry no `List-Unsubscribe` header
(it is never persisted on `MailboxMessage`), so a retrospective sweep can only evaluate the
unattended-sender half of the rule. The unsubscribe half is live for incoming mail and simply cannot
be measured backwards. The true figure is therefore "1 measurable, plus an unknown number of
unsubscribe-bearing messages whose headers were never stored".

This is the same shape as TASK-148 (TASK-140 AC6) and TASK-153 (TASK-135 AC1 / TASK-150 AC4): a
criterion whose number presumed more data than reality holds. TW-005 says such a criterion is
reworded through its own filed task, never silently relaxed.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 TASK-154 AC5 is reworded to: "Measured against the real mailbox: how many currently-stored messages would newly be refused a suggestion under this rule, and EVERY one of them spot-checked — at least three when that many qualify — confirming each really is bulk"
- [x] #2 The reworded criterion records the retrospective limitation: stored rows have no `List-Unsubscribe` header, so a backward sweep evaluates only the unattended-sender half
- [x] #3 With that wording, the 2026-08-20 measurement (58 actionable messages, 1 refused, 1 of 1 spot-checked and confirmed a JOIN job-ad blast) satisfies it, and TASK-154 AC5 is ticked citing this task
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-08-20: reworded in place on TASK-154, carrying both the reason three cannot exist and the retrospective List-Unsubscribe limitation, and ticked against the measurement above.
<!-- SECTION:NOTES:END -->
