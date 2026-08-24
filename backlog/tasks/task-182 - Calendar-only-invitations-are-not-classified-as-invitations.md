---
id: TASK-182
title: Calendar-only invitations are not classified as invitations
status: To Do
assignee: []
labels:
  - backend
  - mailbox
  - bug
dependencies:
  - TASK-135
  - TASK-179
priority: high
ordinal: 182000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found while implementing TASK-179 and confirmed by the coordinator against production, 2026-08-24.
Deliberately left unfixed there rather than guessed at.

TASK-179 fixed the write path so an interview date now reaches `JobLead.interview_at`. It sources the
date from `MailboxMessage.calendar_start` first, and does so **regardless of classification** — which
is what makes the backfill work. The LIVE path is still blind, because a suggestion is only built for
a message classified `interview_invitation`, and the real invitations are not classified that way.

Measured on the owner's production database by `backfill_interview_dates`:

    messages carrying a calendar_start        20
      of those NOT classified as an invitation  19
    messages classified interview_invitation  13

**19 of 20.** A Teams/Outlook meeting invitation arrives with an EMPTY text body — the content is the
iCalendar part, which is exactly why TASK-135 stores `calendar_start` and why
`backfill_message_bodies` exists. `_classify_heuristic` reads `subject + body_text` only, so a
message whose subject is "Einladung zum Kennenlernen per Microsoft-Teams" and whose body is empty
hits no keyword and lands on `recruiter_reply`. One of the two jobs the TASK-179 backfill recovered
(job 723, APC Business Services) came from precisely such a message.

Consequence: every future interview invitation of this shape still produces no `interview_date`
suggestion, so the owner is never offered the date and the Upcoming interviews panel stays empty for
it. The backfill papers over the history; it does not fix tomorrow.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The signal used is stated and justified against a measured production sample, not chosen speculatively — name which messages it would newly classify and which it would not
- [ ] #2 A message carrying a calendar VEVENT that invites the owner to a meeting is classified so that the live path builds an `interview_date` suggestion carrying the date
- [ ] #3 Measured against production with a dry run BEFORE anything changes: how many of the 20 calendar-carrying messages change classification, and what each one becomes. A message changing to `interview_invitation` that is not an interview is a FAILURE of this task, not an acceptable cost
- [ ] #4 Non-interview calendar mail does not become an invitation — a declined meeting, a cancellation, a recruiter's own "hold this slot" and a calendar-bearing newsletter are each checked explicitly and named in the report
- [ ] #5 TASK-163's and TASK-169's guards still hold: no job-board digest and no non-job mail reaches a status-changing classification, verified by the existing tests plus a production re-measurement of the unmatched suggestion counts
- [ ] #6 The 2026-08-23 measurement is repeated after the change: suggestions across the 11 multi-job companies, and how many name the right process
- [ ] #7 Backend suite green
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
This repo's rule, learned the hard way in TASK-162 and TASK-163 and recorded in CLAUDE.md: a
classifier is widened against a measured production example, never speculatively. TASK-162's change
looked right and wanted to demote 26 genuine messages including a real interview thread; TASK-163
fired on 8 of 321 messages and got 2 of 5 suggestions wrong. Both passed their tests first.

So the dry run in AC3 is not a formality — it is the whole task. Produce the list of what would
change before changing anything, and read it.

The tempting shortcut is "has a calendar_start -> interview_invitation". Do not ship that without
AC4's checks: a cancellation carries a VEVENT too, and so does a recruiter proposing a slot for a
role the owner never applied to. `MailboxMessage` already stores `calendar_summary` and
`calendar_organizer` alongside `calendar_start`; whether those separate the cases is an empirical
question this task must answer with numbers.

Note the asymmetry worth preserving: TASK-179's backfill reads the calendar date
classification-independently on purpose. Whatever this task does to the classifier, it must not make
that read narrower, or the backfill loses the 19.
<!-- SECTION:NOTES:END -->
