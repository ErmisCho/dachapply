---
id: TASK-143
title: Only track conversations for jobs still worth acting on
status: In Progress
assignee: []
labels:
  - backend
  - frontend
  - mailbox
priority: high
ordinal: 143000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner instruction 2026-08-19: *"since the Deltia AI (Almetra) - Senior Backend Engineer is marked as
rejected in the job listings board, you no longer have to check and show this conversation up. Show
in general an email conversation is tracked if there is a job listing in the platform relevant to it
that is in open or interview or applied (etc. when I can still do something about it)."*

Measured — the panel is currently showing conversations for jobs the owner has already closed out:

    job 760  Deltia AI (Almetra)   status=rejected   17 messages
    job  34  Hays                  status=rejected   12 messages
    job  44  Takeda                status=archived   12 messages
    job  19  Koerber Pharma        status=archived    7 messages
    job 779  SQUER                 status=rejected    9 messages
    job  23  TU Wien               status=rejected    6 messages

That is six of the twelve busiest jobs, and every one of them is asking the owner to make a decision
about an application that is already over. It is also a straight contributor to TASK-142's freeze:
each of those jobs costs a card, a `/jobs/{id}/mailbox/` request and its share of the 22,543 DOM
nodes.

`JobLead.STATUSES` is `new, reviewed, to_apply, applied, interview, offer, accepted, rejected,
withdrawn, skipped, archived`. The owner's "when I can still do something about it" splits that list.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The actionable set is defined once, named, in the model next to `STATUSES`/`DATED_STATUSES`/`UNAPPLIED_STATUSES` — not repeated as a literal in a view, a service and a component. The proposed split is actionable = `new, reviewed, to_apply, applied, interview, offer, accepted`; not actionable = `rejected, withdrawn, skipped, archived`
- [ ] #2 A conversation whose job is not actionable is not shown in the mailbox review panel: job 760 (rejected) disappears from the panel, verified in a browser and not from the queryset
- [ ] #3 No new suggestion or draft is generated for a message matched to a non-actionable job — "you no longer have to check" means the work stops, not just the display. Verified by test
- [ ] #4 Nothing is deleted and nothing becomes unreachable: the messages, notes and past decisions on a rejected job remain on that job's own detail view. This hides a conversation from the review panel; it does not erase the record
- [ ] #5 A job moving back into an actionable status brings its conversation back, with no re-fetch and no data repair needed — status is a filter, never a destructive action. Verified by test
- [ ] #6 A message matched to a non-actionable job is still visible somewhere the owner can find it, and that place is named. Silently swallowing mail is the failure mode TASK-137 just spent a whole task fixing
- [ ] #7 Existing pending suggestions on now-excluded jobs are handled deliberately: state whether they are dismissed, left pending but hidden, or migrated, and why. There are 4 such suggestions in production today, so this is a real case and not hypothetical
- [ ] #8 Backend tests cover the status gate on generation and on the panel query; `npx tsc --noEmit` and `npm test` clean; the existing suite passes unchanged
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
AC1 exists because this list will be wrong once and then needs changing in one place. `models.py:113-115`
already establishes exactly this pattern with `DATED_STATUSES` and `UNAPPLIED_STATUSES`, both of which
are consumed from the model rather than re-typed.

`accepted` is deliberately in the actionable set in the proposal above: an accepted offer still
produces mail worth reading (start date, paperwork), and the owner's phrasing is about whether they
can still act, not about whether the application is open. If the implementer disagrees, say so and
argue it in the task — do not silently pick the other split.

AC3 is the one with teeth. The gate belongs where suggestions are generated in `services/mailbox.py`,
not only on the read path, or the app will keep drafting replies to rejections nobody will send and
the owner will keep paying for the model call.
<!-- SECTION:NOTES:END -->
