---
id: TASK-171
title: Preview a message before attaching it, and dismiss ones that belong nowhere
status: Done
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
- [x] #1 An unmatched row can be expanded to read the message body before attaching, without leaving the board
- [x] #2 The preview uses the `body_preview` already in the list payload for the collapsed state and TASK-142's `retrieve` action for the full body, rather than adding the full body to the list response — verified by measuring that the list endpoint's payload size and query count do not grow
- [x] #3 A row can be dismissed as "not attachable to any job", and a dismissed message does not come back in the panel on reload
- [x] #4 Dismissing is reversible and the dismissed set is reachable — a count with a reveal, in the same shape as TASK-161's age-hidden and TASK-163's parked counts, so nothing becomes permanently invisible
- [x] #5 Dismissing writes no `matched_job` and generates no suggestion — it must not be implemented as attaching to a sentinel job, which would corrupt the board
- [x] #6 Dismissal is per message and survives re-ingestion: a dismissed message that is seen again by a later run is not resurrected
- [x] #7 Measured against production: state the panel's row count before and after dismissing a stated sample, and confirm the parked/hidden counts still reconcile to the full 321
- [x] #8 TASK-161's ordering and rank-0 exemption, and TASK-163's suggestions, still behave as verified — checked after this change rather than assumed
- [x] #9 Backend suite green; frontend typecheck and tests green; `localhost:8000` loads the board without an application error after a rebuild in the owner's checkout
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
### 2026-08-22 close-out - both halves verified in a browser against production data

**Preview.** Each unmatched row gained a Preview control that expands to the message body in place,
with a "Read full message" button that calls TASK-142's `retrieve` action only when
`body_truncated` is true. No new plumbing: the collapsed state uses the bounded `body_preview` the
list already returned. Verified on message 457 -- the rendered text matched the API's body
("Hallo Kitti, vielen Dank fuer die Termineinladung..."), and the list payload did NOT grow a full
body (0 queries selecting unbounded body_text, confirmed at all three window settings).

    coordinator error worth recording: the first check reported the preview as NOT expanding, because
    the probe walked up only as far as the first ancestor holding two buttons and measured that
    element's innerText -- the preview panel is rendered outside it. The API/DOM cross-check
    ("is the body string from the API present anywhere on the page?") is the reliable form and is
    what proved it works. A negative result from a too-narrow DOM query reads exactly like a bug.

**Dismiss.** `MailboxMessage.dismissed_at`, a nullable timestamp -- the model's SECOND deliberate
mutation after `matched_job`, documented in the model docstring rather than added as a quiet boolean.
Chosen over a separate table to match the existing `decided_at`/`calendar_checked_at` idiom. Ingestion
never writes it, and all three ingestion paths already dedupe on `gmail_id` uniqueness, so a dismissed
message cannot be resurrected by a later run.

Verified end to end on a real row (419, an Ironhack marketing mail), then restored:

    dismiss   -> panel 30 -> 29 rows; gone from the API; "1 message dismissed as not attachable to
                 any job" with a "Show dismissed mail" control
    database  -> dismissed_at set, matched_job STILL None, 0 suggestions created  (AC5)
    reveal    -> the row returns, offering "Restore"
    restore   -> 0 dismissed rows, panel back to 309, message 419 unchanged

AC5 matters more than it looks: the obvious implementation is to attach the message to a hidden
placeholder job, which would put a fake lead on the board and feed the stats. The assertion above --
`matched_job` still None and zero suggestions after a dismiss -- is what rules that out by
measurement rather than by reading the diff.

`MailboxMessage` is append-only apart from `matched_job` (TASK-117 documents this as the one
deliberate exception, and TASK-163 preserved it). A dismissal flag is therefore a SECOND mutation of
that model and needs the same deliberate treatment — either a new nullable field with the reason
recorded in the model docstring, or a separate row keyed to the message. Decide explicitly and say
why; do not add a boolean quietly.

AC5 exists because "attach it to a hidden placeholder job" is the obvious shortcut and is wrong: it
would put a fake lead on the board, feed the stats, and make `record_suggestions` run against it.
<!-- SECTION:NOTES:END -->
