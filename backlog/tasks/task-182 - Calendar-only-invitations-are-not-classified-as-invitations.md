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

## Measured outcome, 2026-08-24 — the chosen option alone was a no-op

The owner's chosen option (read `calendar_summary` for the classifier's EXISTING interview keywords)
was implemented first and measured against production. It changed **0 of 21** calendar-carrying
messages, for two reasons neither the brief nor the coordinator had checked:

- **15 of the 21 summaries are already contained verbatim in the subject or body**, so feeding the
  summary to the classifier a second time cannot change anything by construction. The brief's premise
  that these invitations have an empty body is true of only some of them (139, 701, 702, 1034);
  message 122's body is 1720 chars, 578's is 2912.
- The remaining 6 carry **no keyword `INTERVIEW_KEYWORDS` knows.** That list contains no bare
  `interview` — its entries are phrases: `invite you to an interview`, `schedule an interview`,
  `phone screen`, `technical interview`, `vorstellungsgespräch`.

The implementing agent reported this rather than quietly widening the rule, and the coordinator
re-measured it independently and got the same numbers.

**Scope extended by the coordinator, 2026-08-24:** one new term, a bare `interview`, **structurally
scoped to `calendar_summary`** so it cannot match a subject or a body. Reading it from the body was
rejected outright — ATS boilerplate, newsletters and rejection letters all contain the word, and that
would be exactly the unmeasured widening the WEAK/STRONG comment block exists to prevent.

Measured result across all 1133 messages: exactly **5** move to `interview_invitation` — 175, 179
(SQUER), 391 (zooplus follow-up), 421 (Ironhack), 578 (Online-Interview) — and nothing else.
All four community meetups stay out, as does `Meet Ermis`. The owner's constraint is preserved:
`meet` was deliberately NOT added, because it would catch three of the four meetups.

Still not caught, and correctly so under the owner's conservative choice: `Hays - Austausch
Jobmöglichkeit`, `Formunauts - On Site`, `Initial call`, `Kennenlernen`, `IV:`. The Formunauts case
turned out to be a **matching** defect rather than a keyword one and is filed as TASK-186.
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
