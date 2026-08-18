---
id: TASK-120
title: Show a job's whole email history and its notes where the decision is made
status: Done
assignee:
  - '@claude'
labels:
  - frontend
  - backend
  - mailbox
priority: high
ordinal: 120000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner request 2026-08-18: *"I should be able to see all the related email threads so far and also my
notes."*

Deciding whether an email really is a rejection depends on what came before it. Today the decision
card shows exactly one message in isolation. The job's earlier mail exists — `MailboxMessage.matched_job`
is populated and `GET /api/jobs/{id}/mailbox/` already returns every message for a job, newest
first — but only the pending ones surface, and the job's `ApplicationNote`s are not in that payload
at all.

### "Threads" is a promise the schema cannot keep yet, and this task says so

There is no thread. `RawMessage.references` is transient (`mailbox.py:81`, consumed only by
`build_reply_mime` and never stored) and Gmail's `threadId` is fetched and dropped (`mailbox.py:395`).
`MailboxMessage.message_id` is persisted but with no `In-Reply-To`/`References` counterpart there is
no parent pointer to chain on, so a real threaded exchange cannot be reconstructed from what is
stored.

What IS available is every message matched to this job, in order. That is the honest deliverable
here, and it is most of the value. Genuine thread grouping arrives with TASK-121, which persists
Gmail's `threadId` for its own reasons; this task must be built so that grouping can be switched on
later without redesigning the view.

Ordering matters and the obvious key is wrong: `MailboxMessage.Meta.ordering` is `['-uid']`, and for
Gmail-API rows `uid` is a locally assigned sequence number minted in processing order
(`mailbox.py:1357`), not a received time. `received_at` is the honest sort key.

### The notes half

`ApplicationNote` already has a `recruiter_message` type, and since TASK-117 every confirmed
suggestion writes one naming the email that caused the change. Those notes are the job's memory of
why it moved, and they belong beside the next decision. `GET /api/jobs/{id}/notes/` exists and
returns them newest-first.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The decision view for a job shows every mailbox message matched to that job, not only the ones with pending suggestions — including messages that produced no suggestion and messages whose reply was blocked, each with its classification
- [x] #2 Messages are ordered by when they were RECEIVED, not by `uid`. `received_at` is nullable, so the fallback when it is null is chosen deliberately and stated in the code, rather than letting null sort arbitrarily
- [x] #3 The job's `ApplicationNote`s appear in the same view, newest first, each showing its type in words — a `recruiter_message` note written by a confirmation must be distinguishable from a note the owner typed
- [x] #4 Notes reach the client without a second round trip per job: they are part of the per-job mailbox payload, verified by counting requests in the browser network panel, not by reading the code
- [x] #5 The view states plainly that it is a per-job list rather than a reconstructed thread, and the code says why (`references` and `threadId` are not persisted) — so the next reader does not assume threading was attempted and failed
- [x] #6 Nothing here widens access: the payload stays behind the same `accessible_jobs` scoping as the job itself, verified against a real API response with a second user, not by reading the serializer
- [x] #7 A job with many messages does not make the panel unusable — long histories are bounded or scrollable, measured at 360px
- [x] #8 Backend tests cover the notes in the payload, the received-time ordering including the null case, and the scoping; `npx tsc --noEmit` and `npm test` clean
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
`JobLeadViewSet.mailbox` (`views.py:622`) is the natural home — it already prefetches `draft` and
`suggestions` and is `accessible_jobs`-scoped through `get_object()`. Adding notes there is a
serializer change plus one prefetch, not a new endpoint.

AC3's "distinguishable" matters more than it looks. `openNoteModal` currently treats notes as a
single editable blob and can pick up a `recruiter_message` note as "the" note — see TASK-123, which
must land first or at the same time, or this view will show the owner an audit note that the board's
own note button can silently overwrite.

Do not reconstruct threads by normalising subject lines. `_reply_subject`'s `Re:` stripper
(`mailbox.py:884`) is the closest existing thing and it is a guess; two unrelated rejections from the
same company would merge. Wait for the real `threadId` from TASK-121.
<!-- SECTION:NOTES:END -->

## Outcome (2026-08-18)

`GET /api/jobs/{id}/mailbox/` now returns `{messages, notes}` instead of a bare array, ordered by
`F('received_at').desc(nulls_last=True)` with the null choice stated in a comment — `uid` is a
locally assigned sequence number for Gmail-API rows, not a received time, so it was the wrong key.
`JobMailboxTrigger` renders an "Email history" list (every matched message, its classification and
its Gmail link) and a "Notes" list with each note's type in words.

MEASURED:

- **AC4** — notes arrive in the same payload; response shape confirmed as `["messages","notes"]`
  from one request, no per-job second round trip.
- **AC5** — the view states it verbatim: *"Every email matched to this job and every note on it, most
  recent first. This is a flat per-job list, not a reconstructed conversation thread."*
- **AC6** — a second user gets 404 with no body content (backend test asserts against the response,
  not the serializer).
- **AC7** — at a 360px viewport the popup measures 281px, fits, scrolls internally
  (`overflow-y: auto`), and the page itself does not overflow (`scrollWidth` 343 ≤ 360).

507 backend tests, `npx tsc --noEmit` clean, 52 frontend tests.

### Found while verifying, and filed rather than absorbed

The history is only reachable while a suggestion is **pending**, because the board indicator is keyed
to pending suggestions. A job whose decisions are all made shows no indicator and its history becomes
invisible — measured: `triggersOnBoard ["Email decision needed for Acme GmbH"]`,
`broadpinHasTrigger false`, while Broadpin had a message, a blocked draft and two notes. That is
backwards for a feature whose point is history, and it is **TASK-126**, not a quiet fix here: the
board does not know which jobs have mail without either a new field on the jobs list (which TASK-91
exists to keep slim) or an extra request, and that is a decision to record rather than take in
passing.
