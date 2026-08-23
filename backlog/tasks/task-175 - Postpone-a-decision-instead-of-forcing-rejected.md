---
id: TASK-175
title: Postpone a decision instead of forcing rejected
status: To Do
assignee: []
labels:
  - backend
  - frontend
  - mailbox
  - ux
dependencies: []
priority: high
ordinal: 175000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner, 2026-08-23: *"in the email decisions, there are some emails that should be postponed yet,
cause the company said I will get back to you in a few weeks or so, so maybe I can just reschedule a
follow up and set the status to pending or something rather than rejected."*

A decision card today offers only the suggestion the classifier produced, with Yes / No. For a
message that says *"we will come back to you in a few weeks"*, both answers are wrong:

- **Yes** marks a live application `rejected`. It is not rejected; it is waiting.
- **No** dismisses the suggestion and the message leaves no trace, so the waiting is not recorded
  anywhere and nothing will remind the owner in three weeks.

So the one genuinely correct outcome — *this is alive, ask me again later* — cannot be expressed.

**The app already models "waiting", and it is not a status.** `JobLead.feedback_due_date` is the
waiting-for-feedback clock; `MailboxSuggestion.TYPES` already includes `feedback_clear` to clear it,
and `build_suggestions` sets it elsewhere. What is missing is the opposite action: PUSH the clock
out, from a decision card, in one click.

**Why this should not be a new `pending` status, despite the owner's phrasing.** `JobLead.STATUSES`
is a pipeline — new, reviewed, to_apply, applied, interview, offer, accepted, rejected, withdrawn,
skipped, archived — and "waiting" is not a stage in it. The owner can be waiting after applying and
waiting again after an interview; it is an annotation ON a stage, not a stage. A `pending` status
would collapse two independent dimensions into one field, and it would corrupt the funnel counts and
`DATED_STATUSES` staleness logic, which assume the status says where the application actually got to.
Keeping the status and moving the date says exactly what happened and keeps both dimensions honest.
Record this reasoning when implementing; the owner's instinct about the BEHAVIOUR is right, and only
the storage choice differs.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A decision card offers a third action alongside Yes / No — postpone — that sets the job's `feedback_due_date` forward and does NOT change the job's status
- [ ] #2 The owner chooses when: at minimum a small set of sensible intervals (e.g. 1, 2, 4, 8 weeks) or a date, rather than a single hardcoded delay
- [ ] #3 Postponing resolves the original suggestion so the same card does not reappear unresolved on the next load, and the resolution is distinguishable from both a confirm and a dismiss
- [ ] #4 The postponement is visible afterwards: the job shows its new waiting-until date wherever `feedback_due_date` is already surfaced, and the owner can tell a postponed application from one never waited on
- [ ] #5 When the date arrives, the job appears wherever overdue feedback already surfaces today — the existing feedback-due machinery is reused rather than a second reminder system built
- [ ] #6 No new `JobLead` status is added; the reasoning above is recorded in the implementation notes, or a measured argument is given for why a status is genuinely required after all
- [ ] #7 A postpone is reversible: the owner can still later confirm the original suggestion or reject the job, and postponing does not lock the decision away
- [ ] #8 Verified in a browser end to end on a synthetic job created for the purpose and deleted afterwards: postpone from a real card, observe the date set and the status unchanged, then observe it resurface when the date is past
- [ ] #9 Backend suite green; frontend typecheck and tests green; `localhost:8000` loads the board without an application error after a rebuild in the owner's checkout
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
`MailboxSuggestion.TYPES` is `status_change`, `interview_date`, `feedback_clear`. This likely wants a
fourth (`feedback_postpone` or similar) so the action is recorded in the same ledger as every other
decision, rather than being a side-effect the suggestion log cannot explain later.

Do not let the classifier's original guess constrain the offered actions. The suggestion says
`rejection` because a keyword matched; the owner reading the mail is the better judge, and this task
exists precisely because the classifier's binary was wrong for this class of message. Related:
TASK-168 is fixing several such misclassifications, but no classifier will get "we will come back to
you in a few weeks" reliably right, so the postpone action is worth having regardless of how good the
classification gets.
<!-- SECTION:NOTES:END -->
