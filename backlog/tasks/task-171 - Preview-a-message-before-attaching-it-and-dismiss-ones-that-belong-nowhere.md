---
id: TASK-171
title: Preview a message before attaching it, and dismiss ones that belong nowhere
status: To Do
assignee: []
labels:
  - frontend
  - backend
  - mailbox
  - ux
dependencies:
  - TASK-163
priority: high
ordinal: 171000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Two owner requests, 2026-08-21, filed together because they are the same row in the same panel and
are the two things missing before the attach decision is a decision rather than a guess:

1. *"give an option to just disregard emails as attachable to a job"*
2. *"allow for a preview of the email that you want me to bind with a job listing"*

**Preview.** Today an unmatched row shows only sender, subject and classification. The owner is asked
to bind that message to a job — an action that writes `matched_job` and generates status-change
suggestions — with no way to read what the message actually says. Most of the machinery already
exists and is simply not surfaced: the list endpoint already returns a bounded `body_preview` (the
`Substr` annotation TASK-142 added), and TASK-142 also added a `retrieve` action described in its own
docstring as "the full-body counterpart to unmatched's" preview. So this is largely a rendering task,
not new plumbing.

**Dismiss.** Measured against production 2026-08-21: **204 of the 321** unmatched rows (64%) name no
tracked company at all, and **30 of the 41** high-consequence rows are about applications that were
never on the board. TASK-163 parks the unidentifiable ones behind a count, which stops them drowning
the panel but leaves them permanently in it. There is currently no way to say "this one belongs
nowhere" — so the same mail is re-read on every visit, and the parked count never goes down.

Note the interaction with TASK-166 (create a job from a message): dismiss and create-a-job are the
two honest endings for mail about an untracked application. Dismiss is the cheap one and does not
block on TASK-166.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 An unmatched row can be expanded to read the message body before attaching, without leaving the board
- [ ] #2 The preview uses the `body_preview` already in the list payload for the collapsed state and TASK-142's `retrieve` action for the full body, rather than adding the full body to the list response — verified by measuring that the list endpoint's payload size and query count do not grow
- [ ] #3 A row can be dismissed as "not attachable to any job", and a dismissed message does not come back in the panel on reload
- [ ] #4 Dismissing is reversible and the dismissed set is reachable — a count with a reveal, in the same shape as TASK-161's age-hidden and TASK-163's parked counts, so nothing becomes permanently invisible
- [ ] #5 Dismissing writes no `matched_job` and generates no suggestion — it must not be implemented as attaching to a sentinel job, which would corrupt the board
- [ ] #6 Dismissal is per message and survives re-ingestion: a dismissed message that is seen again by a later run is not resurrected
- [ ] #7 Measured against production: state the panel's row count before and after dismissing a stated sample, and confirm the parked/hidden counts still reconcile to the full 321
- [ ] #8 TASK-161's ordering and rank-0 exemption, and TASK-163's suggestions, still behave as verified — checked after this change rather than assumed
- [ ] #9 Backend suite green; frontend typecheck and tests green; `localhost:8000` loads the board without an application error after a rebuild in the owner's checkout
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
`MailboxMessage` is append-only apart from `matched_job` (TASK-117 documents this as the one
deliberate exception, and TASK-163 preserved it). A dismissal flag is therefore a SECOND mutation of
that model and needs the same deliberate treatment — either a new nullable field with the reason
recorded in the model docstring, or a separate row keyed to the message. Decide explicitly and say
why; do not add a boolean quietly.

AC5 exists because "attach it to a hidden placeholder job" is the obvious shortcut and is wrong: it
would put a fake lead on the board, feed the stats, and make `record_suggestions` run against it.
<!-- SECTION:NOTES:END -->
