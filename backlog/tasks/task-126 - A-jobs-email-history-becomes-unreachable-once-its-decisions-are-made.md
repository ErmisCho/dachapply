---
id: TASK-126
title: A job's email history becomes unreachable once its decisions are made
status: To Do
assignee:
  - '@claude'
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
- [x] #1 A job with mailbox history but NO pending suggestion can still reach its email history and notes from the board, verified in a browser on a job whose suggestions are all decided
- [x] #2 The two states are visually distinguishable: "a decision is waiting for you" must not look the same as "there is history to read". A single undifferentiated icon on every job with any mail would train the owner to ignore the one that needs action
- [x] #3 A job with no mailbox history at all shows no indicator — the board must not grow an inert icon on every row
- [x] #4 Whatever tells the board which jobs have history does not add a request per row, and does not measurably slow the jobs list. If it needs a new field on the list response, that is a deliberate decision recorded in the notes, because TASK-91 exists to keep that response slim
- [ ] #5 The indicator keeps every property TASK-117 AC5 established and TASK-81/TASK-102 fought for: a real `<button aria-expanded>` in the tab order, >=44px, click/tap/Enter open, Escape close, hover as an extra only — re-verified by keyboard, not assumed from the fact that it was true before
- [x] #6 `npx tsc --noEmit` and `npm test` clean
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

## Progress (2026-08-18)

`has_mailbox_history` is an `Exists()` annotation on the jobs-list queryset, exposed only on
`JobLeadListSerializer` — the recorded AC4 decision: no request per row, and the detail response
stays as slim as TASK-91 wants. The frontend combines it with the pending-suggestions list through a
pure `mailboxIndicatorState(hasPending, hasHistory) -> 'pending' | 'history' | null`, so a pending
decision always outranks stale history, and a job with no mail renders nothing at all.

Backend tests cover all three states, including the exact reported bug: a job whose only suggestion
is already decided still reports `has_mailbox_history: true`.

### Not verified

**AC1, AC2 and AC5** need a browser: that a decided-only job's indicator is reachable, that the two
states are visually distinguishable at rest (implemented as a persistent amber treatment for pending
versus the original quiet slate for history-only), and that the trigger keeps its `aria-expanded`,
44px target, Escape-close and hover-as-extra contract. Deferred to the next browser pass rather than
claimed.

## Progress (2026-08-18)

MEASURED in a browser with three deliberately different rows:

    Zeta AG    (no mail at all)      -> no indicator                      (AC3)
    Deltia AI  (suggestion decided)  -> "Email history for Deltia AI"     (AC1)
    zooplus    (suggestion pending)  -> "Email decision needed for zooplus"

- **AC1** — the decided-only job now has an indicator at all, which was the whole defect; clicking it
  opens *"Email history — No pending email decisions for this job."*
- **AC2** — the two states differ in three ways at once: the accessible label, the at-rest styling
  (an amber `bg-` treatment for pending versus text-only for history), and the popup's own header
  (*"Email needing your decision"* vs *"Email history"*). Not one undifferentiated icon.
- `has_mailbox_history` came back correctly per job from the list endpoint — false only for the job
  with no mail.

### AC5 not closed

The indicator is a real `<button aria-expanded>` measuring 44x44 and opens on click, all measured.
But AC5 explicitly demands keyboard re-verification "not assumed from the fact that it was true
before", and Tab/Enter could not be driven reliably this round — focus did not survive between
automation calls and the renderer eventually froze. Left unchecked rather than claimed on the
strength of the element type.
