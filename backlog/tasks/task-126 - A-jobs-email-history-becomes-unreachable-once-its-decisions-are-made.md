---
id: TASK-126
title: A job's email history becomes unreachable once its decisions are made
status: To Do
assignee: []
labels:
  - frontend
  - mailbox
  - bug
dependencies:
  - TASK-117
  - TASK-120
priority: high
ordinal: 126000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found by measurement while verifying TASK-120 in a browser, not by reading code.

TASK-120 built the per-job email history and notes view, and it works: the popup lists every message
matched to the job, its classification, its Gmail link, and the job's notes with their types. But the
only way to open it is the board-row indicator, and that indicator renders only when the job has a
**pending** `MailboxSuggestion`.

Measured on the verification board:

    triggersOnBoard:      ["Email decision needed for Acme GmbH"]
    broadpinHasTrigger:   false

Broadpin at that moment had one mailbox message, a blocked draft, two notes and a confirmed
suggestion. All of it invisible from the board, because its decision had been made.

So the history is reachable exactly while a decision is pending, and disappears the moment you act on
it — which is backwards. The owner's original request was *"I should be able to see all the related
email threads so far and also my notes"*; "so far" is precisely the decided ones.

This is not a defect in TASK-120's view. It is the entry point being keyed to the wrong condition.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A job with mailbox history but NO pending suggestion can still reach its email history and notes from the board, verified in a browser on a job whose suggestions are all decided
- [ ] #2 The two states are visually distinguishable: "a decision is waiting for you" must not look the same as "there is history to read". A single undifferentiated icon on every job with any mail would train the owner to ignore the one that needs action
- [ ] #3 A job with no mailbox history at all shows no indicator — the board must not grow an inert icon on every row
- [ ] #4 Whatever tells the board which jobs have history does not add a request per row, and does not measurably slow the jobs list. If it needs a new field on the list response, that is a deliberate decision recorded in the notes, because TASK-91 exists to keep that response slim
- [ ] #5 The indicator keeps every property TASK-117 AC5 established and TASK-81/TASK-102 fought for: a real `<button aria-expanded>` in the tab order, >=44px, click/tap/Enter open, Escape close, hover as an extra only — re-verified by keyboard, not assumed from the fact that it was true before
- [ ] #6 `npx tsc --noEmit` and `npm test` clean
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
The board currently derives the indicator from the pending-suggestions list it already loads
(`/mailbox-suggestions/`, which is pending-only by default), so "has any mail" is genuinely not known
client-side today. That is the whole cost of this task, and AC4 is where it gets decided.

Cheapest honest options, in ladder order:
1. A count or boolean on the jobs list response (`JobLeadListSerializer`) — one annotated query, no
   extra round trip, but it widens the response TASK-91 was filed to keep slim.
2. One extra request returning just the job ids that have mailbox messages — leaves the list
   untouched, costs one request per board load.
3. Reuse the existing suggestions request by having it return decided suggestions too — smallest
   diff, but it changes what that endpoint means and would pull decided rows into the panel unless
   carefully filtered.

Option 1 is probably right, and AC4 exists to force that to be a recorded decision rather than a
drive-by.

AC2 matters more than it looks. TASK-117's indicator means "act on this". If it starts also meaning
"there is something to read", the actionable signal is diluted, and the panel at the top of the
dashboard is already the place decisions are surfaced — this indicator's second job is reference,
not action.
<!-- SECTION:NOTES:END -->
