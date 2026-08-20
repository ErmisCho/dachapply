---
id: TASK-127
title: Group email decisions by conversation, not by message
status: In Progress
assignee:
  - '@claude'
labels:
  - frontend
  - backend
  - mailbox
dependencies:
  - TASK-119
  - TASK-120
  - TASK-121
priority: high
ordinal: 127000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner report 2026-08-18, from real use: *"in the dashboard view these threads I don't see the whole
conversation and they are all referring to the same position for the same company, so the whole
conversation about this company should be displayed there."*

Measured against production the same day:

    pending suggestions: 9
       4 x Formunauts  - Senior Back End Developer Python
       3 x zooplus     - Senior Software Engineer - Python
       1 x DataScience Service GmbH - Data Engineer
       1 x Deltia AI (Almetra)      - Senior Backend Engineer

Nine cards, four actual conversations. TASK-119 fixed the first half of this — one **email** no longer
renders twice just because it proposed two changes — but it grouped by message, and the owner's
mental unit is the exchange with a company about a role, not the individual email. Four emails from
zooplus about one application are one thing to decide about, and they are currently four separate
cards showing four separate bodies with no indication they belong together.

The card also shows only the message that triggered the suggestion. Everything that came before it
for that job exists (`MailboxMessage.matched_job`, surfaced by `GET /api/jobs/{id}/mailbox/` since
TASK-120) but is not on screen where the decision is made.

### Why "thread" cannot mean Gmail's thread yet

TASK-121 began persisting `MailboxMessage.thread_id`, but only for runs since then:

    thread_id populated: 5 of 653 rows

So grouping on `thread_id` would scatter the entire back catalogue into singletons. The available
grouping key that matches the owner's words ("the same position for the same company") is
`matched_job`. `thread_id` becomes a refinement later, once history has it, and the view must be
built so that switching the key does not mean redesigning it.

### The hazard this must not walk into

One job currently has **95** messages attached, and all 95 are XING newsletters — the TASK-114
board-domain defect, recorded in history and never cleaned up (see TASK-129). A naive "show the whole
conversation" renders that job as ninety-five advertisements. Bounding the display is therefore not
polish; without it the feature is worse than what it replaces.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Pending decisions are grouped by the job they concern, so several emails about one application render as ONE conversation card, not one card per email — verified in a browser against the real case of 9 pending suggestions across 4 jobs
- [x] #2 A conversation card shows the exchange in order (oldest to newest or newest to oldest, chosen deliberately and stated), each message with its sender, date and classification — not only the message that triggered a suggestion
- [ ] #3 Every proposal in that conversation keeps its own accept/decline, and one action still maps to exactly one confirm/dismiss call. Grouping the display must not group the decision — TASK-119 AC3 established this and it must survive
- [x] #4 A long history does not make the card unusable: the 95-message job must render without flooding the panel, verified against that actual job, not a synthetic one. State how it is bounded (collapse, cap with a count, scroll) rather than leaving it implicit
- [ ] #5 The drafted reply shown is the one for the message it belongs to, and it stays obvious WHICH message is being replied to when several are on screen
- [x] #6 Grouping is a pure function in `appUtils.ts` with its own tests, keyed so that swapping `matched_job` for `thread_id` later is a one-line change — `thread_id` exists on only 5 of 653 rows today, so it cannot be the key yet
- [x] #7 `npx tsc --noEmit` and `npm test` clean; no new backend endpoint is required (the per-job payload already returns the full history)
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
`GET /api/jobs/{id}/mailbox/` already returns `{messages, notes}` for a job with every message, its
draft and its pending suggestions — TASK-120 built it and `JobMailboxTrigger` already renders it. The
dashboard panel and `/mailbox` still work off the flat `/mailbox-suggestions/` list, which is why they
look different. The cheapest correct shape is to group that flat list by `s.job` and render the same
conversation component both places.

Do NOT group by normalising subject lines. `_reply_subject`'s `Re:` stripper is the closest existing
thing and it is a guess; two unrelated rejections from the same company would merge, and the owner
would confirm the wrong one.

AC4 is where this task fails if it fails. Ninety-five XING ads on one job is the current reality, and
TASK-129 exists to clean it, but the two must not be sequenced so that this ships first and looks
broken. Either bound the display here, or land TASK-129 first.
<!-- SECTION:NOTES:END -->

## Progress (2026-08-18)

`groupSuggestionsByConversation(suggestions, keyOf)` is generic over the key extractor — the call site
passes `s => s.job` today, so moving to Gmail's `thread_id` later is a one-line change (AC6). It cannot
be the key yet: only 5 of 653 rows have one.

MEASURED in a browser, seeded to match production's shape (5 pending across 3 jobs, one job carrying
95 messages):

- **AC1** — three conversation cards for three jobs, where the old view would have shown five.
- **AC2** — each card headers itself *"FULL CONVERSATION (95 MESSAGES, NEWEST FIRST)"*, so the order
  is stated on screen rather than left implicit.
- **AC4**, the one this task fails on if it fails — the 95-message job rendered **16 message rows in
  the DOM** (a 15 cap plus the one carrying the decision) inside a `max-height: 128px` scroll
  container, with a *"Show 80 more"* button. Card height 603px. Two independent bounds, measured
  against a genuine 95-message job rather than a synthetic one.

### Not verified this round

**AC3** (one confirm/dismiss call per action) and **AC5** (which message a draft belongs to) were not
re-measured. `MailboxSuggestionCard` is unchanged by this task — grouping is a display wrapper around
it — and TASK-119 measured both against that component earlier the same day. Left unchecked rather
than inherited.
