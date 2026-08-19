---
id: TASK-142
title: The dashboard freezes the owner's computer
status: In Progress
assignee: []
labels:
  - backend
  - frontend
  - performance
priority: high
ordinal: 142000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner report 2026-08-19: *"since you collected so many emails, viewing the website freezes my
computer."*

Measured on the board, and it is not subtle:

    /api/mailbox-messages/unmatched/   10,479 ms      <- one request, ten and a half seconds
    /api/jobs/36/mailbox/               3,520 ms
    /api/jobs/37/mailbox/               2,892 ms
    /api/jobs/353/mailbox/              2,822 ms
    /api/jobs/273/mailbox/              2,800 ms
    ... 11 mailbox requests fired on a single dashboard load

    DOM nodes, whole page    35,156
    DOM nodes, mailbox panel 22,543      <- 64% of the page is this one panel
    conversation cards            9
    message rows                127
    expanded message bodies      98

The unmatched endpoint serialises **763 messages carrying 1,796,060 characters of body text** into
one response. Nothing paginates it, nothing truncates the bodies, and the dashboard asks for it on
load. Before TASK-132 backfilled bodies this response was nearly empty, which is why it was never a
problem before and is a severe one now.

The panel then renders every conversation for every job with a pending suggestion, with every message
expanded, on a dashboard the owner opens to see a board.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The unmatched endpoint is bounded: it does not return 763 full message bodies in one response. State the bound (page size, body truncation, or both) and what the client does to reach the rest
- [ ] #2 Measured: `/api/mailbox-messages/unmatched/` responds in under 1 second against the real 940-message database. 10,479 ms is the number to beat, and this is measured in the browser's own resource timing, not estimated from a queryset
- [ ] #3 Total DOM nodes on the board drop below 10,000 with the mailbox panel present. 35,156 total / 22,543 in the panel are the numbers to beat
- [ ] #4 The dashboard does not fire 11 mailbox requests on load. State how many it fires and why that number
- [ ] #5 A conversation is still fully readable when the owner opens it — this is a bound on what renders unasked, not a feature removal. Whatever is collapsed must be reachable in one interaction
- [ ] #6 The board remains usable while mail is loading: no synchronous work on the main thread long enough to freeze the page, verified by measuring the board's interactivity with the panel present
- [ ] #7 No message is deleted and no message becomes unreachable to reach a number — bounding a response is not the same as dropping data, and the unmatched list is where TASK-137's 73 detached messages now live
- [ ] #8 Backend tests cover the bound and its pagination; `npx tsc --noEmit` and `npm test` clean; the existing suite passes unchanged
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Three separate costs are stacked here and they need separating before anything is optimised: the
unmatched endpoint's payload (1.8M characters), the eleven per-job requests, and the 22.5k rendered
nodes. Fixing only one leaves a page that still freezes.

The per-job requests come from the panel mapping every suggestion group to a
`JobMailboxConversationCard` which fetches on mount (`useEffect` -> `/jobs/{id}/mailbox/`). TASK-143
reduces how many of those cards exist at all by filtering to actionable jobs; do not double-solve that
here, but do not depend on it either — the fix must hold when the owner has thirty active
applications.

`body_text` is the payload. The unmatched list shows sender, subject and classification — it does not
need the body at all until a row is opened. A serializer that omits or truncates `body_text` for the
list is the smallest honest fix and needs no pagination to beat AC2, though AC1 asks for the bound to
be stated either way.
<!-- SECTION:NOTES:END -->
