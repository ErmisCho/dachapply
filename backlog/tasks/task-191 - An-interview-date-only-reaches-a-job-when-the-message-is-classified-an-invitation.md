---
id: TASK-191
title: An interview date only reaches a job when the message is classified an invitation
status: To Do
assignee: []
labels:
  - backend
  - mailbox
dependencies:
  - TASK-186
priority: medium
ordinal: 191000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Reported by the agent implementing TASK-186 as a gap it deliberately did not close, and it is right
that it needed its own measured task.

`build_suggestions` proposes an `interview_date` only when `classification == 'interview_invitation'`.
After TASK-186, messages 641 and 664 are correctly **matched** to job 535, but they classify
`recruiter_reply` — their VEVENT summary reads "Formunauts - On Site", which TASK-182 deliberately did
NOT admit as an interview keyword, because admitting "on site" would have caught things that are not
interviews.

So the date reaches the job only through `backfill_interview_dates`, which **is not called from any
automatic path**. A future rescheduled invitation of the same shape will be matched correctly and
still leave `interview_at` empty until someone runs a management command.

That is the exact failure this whole thread started with: the owner had an on-site interview two days
away that the board could not see.

**Why the obvious fix is not obviously right.** Widening `build_suggestions` to propose a date from
any matched calendar-carrying message would fire on roughly 10 of the 21 calendar rows, including
Hays' "Austausch Jobmöglichkeit" — a recruiter catch-up, not an interview. That is the indiscriminate
widening the owner explicitly rejected when they chose TASK-182's conservative option, so it needs its
own dry run rather than an argument.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A matched, calendar-carrying message can put its date on the job without a human running a management command, or the reason it must not is stated with the case that breaks
- [ ] #2 Measured against production before and after: which of the 21 calendar-carrying messages would produce an `interview_date` suggestion, named individually. A non-interview producing one is a FAILURE, not an acceptable cost
- [ ] #3 The four community meetups and the recruiter catch-ups (Hays "Austausch Jobmöglichkeit") are checked by name and do NOT produce an interview date
- [ ] #4 TASK-182's conservative keyword choice is not reversed — if a date now flows from a message the classifier does not call an invitation, state exactly what carries that decision instead
- [ ] #5 `backfill_interview_dates` still works and stays dry-run-by-default; this removes the NEED to run it, not the option
- [ ] #6 Verified on the real thing: clear job 535's `interview_at`, run only the automatic path, and show the date arrives
- [ ] #7 Backend suite green
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
The signal that separates these is probably not the calendar summary at all — TASK-182 already mined
that. It may be that a message matched to a job **already in `interview` status** is different from
one matched to a job in `applied`: the process is known to be at the interview stage, so a meeting
with that employer is far more likely to be the interview. That is a hypothesis with a testable
shape, not a design; measure it before building it.

Do not reach for the LLM path. All 21 calendar rows are `evaluator='heuristic'`, so changing the
prompt would be an unmeasured widening of a path none of them uses.
<!-- SECTION:NOTES:END -->
