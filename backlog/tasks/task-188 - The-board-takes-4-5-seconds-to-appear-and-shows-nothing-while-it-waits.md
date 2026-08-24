---
id: TASK-188
title: The board takes 4.5 seconds to appear and shows nothing while it waits
status: To Do
assignee: []
labels:
  - backend
  - frontend
  - performance
  - ux
dependencies:
  - TASK-187
priority: high
ordinal: 188000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner, 2026-08-24: *"the job listings loading everytime the home page loads takes like 5 seconds, but
it should happen immediately, and also while loading it should be showing a loading table. make the
transition look polished and professional."*

Measured by the coordinator in the browser on the owner's own board, not estimated. Resource timings
from a cold reload:

```
domContentLoaded                                    454 ms   <- the shell is already fast
auth/me/                       475 ->  1011 ms   (  536 ms,   1 KB)
  ... every other request waits for it ...
mailbox-suggestions/          1015 ->  1976 ms   (  961 ms, 243 KB)
jobs/feedback-due/            1015 ->  1626 ms   (  612 ms,   1 KB)
auth/friend-requests/         1015 ->  1670 ms   (  655 ms,   0 KB)
jobs/            (second call)1015 ->  2465 ms   ( 1450 ms,  71 KB)
stats/                        1015 ->  3519 ms   ( 2504 ms,   4 KB)
jobs/            (board)      1015 ->  4528 ms   ( 3513 ms, 393 KB)   <- the long pole
                                                   board usable ~4.5 s
```

Four distinct faults, and they need separating because fixing only the obvious one will not deliver
the owner's "immediately":

1. **A serial gate.** Nothing starts until `auth/me/` resolves at 1011 ms. A whole second passes
   before the board request is even issued.
2. **`/api/jobs/` is 3.5 s for 393 KB over 69 rows** — 5.7 KB per row. TASK-187 already measured part
   of the cause: **69 `auth_user` SELECTs for 69 rows** from four `SerializerMethodField`s walking
   foreign keys the queryset never joined. That is a dependency of this task, not a duplicate of it —
   TASK-187 is the query count, this is the whole experience.
3. **The board fetches jobs twice** — 393 KB and 71 KB, both starting at 1015 ms. Whatever the second
   call is for, two round trips for job data on one page load needs a reason or removal.
4. **Nothing is shown while waiting.** No skeleton, no spinner on the table — the owner watches empty
   chrome for four and a half seconds and cannot tell whether the app is working.

The payload deserves its own look. `JobLeadListSerializer` already excludes `raw_description` and
`original_source_text`, and `JobEvaluationListSerializer` already drops `structured_json_raw`
(~3.7 KB per evaluation) precisely because of this. 5.7 KB per row says something else has grown
since.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Measured before and after in a browser on a real board, as a table of resource timings like the one above — a stated number, not "feels faster"
- [ ] #2 The board's first row is on screen in under 1.5 s on the owner's machine, or the shortfall is measured and its remaining cause named
- [ ] #3 The `auth/me/` serial gate is removed or justified: the board request must not wait on an unrelated request that returns 1 KB
- [ ] #4 `/api/jobs/` issues a constant number of queries regardless of row count (TASK-187), proven by a test that fails on the pre-fix code
- [ ] #5 The duplicate `jobs/` request is removed, or the reason both are needed is recorded with what each one feeds
- [ ] #6 The list payload is measured per row before and after; anything dropped is named, and nothing the board actually renders is dropped
- [ ] #7 A skeleton table is shown while loading — same column layout and row height as the real table, so the transition does not jump
- [ ] #8 The skeleton does not flash on a fast load: it appears only if loading exceeds a stated threshold, and once shown stays long enough not to strobe
- [ ] #9 The transition from skeleton to real rows does not shift layout — first-row top measured in both states and equal
- [ ] #10 Verified at desktop width and stated for the 360px card layout, which renders instead of the table (TASK-147 mounts exactly one)
- [ ] #11 TASK-165, TASK-139, TASK-167 and TASK-178's note markers all still hold, re-measured after the change
- [ ] #12 Backend suite green; frontend typecheck and tests green; `localhost:8000` loads the board after a rebuild in the owner's checkout
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
**Measure before choosing a fix.** The 3.5 s is not yet attributed: TASK-187's 69 `auth_user` queries
are known, but nobody has measured how much of the wall clock they actually cost against a remote
Neon database versus how much is serialization of a 393 KB payload. Those two have completely
different fixes, and guessing between them is the failure this repo keeps recording. Django's
`connection.queries` timing and a `--durations` profile of the serializer are both cheap.

Note the database is remote (Neon), so per-query latency dominates in a way it would not on a local
Postgres — 72 round trips at even 40 ms is 2.9 s on its own. That is a hypothesis with a number
attached, and it is testable; do not ship it as a conclusion.

The skeleton is the smaller half and must not become the whole task. A skeleton that hides a 4.5 s
wait is a worse outcome than a 1 s board with no skeleton — AC2 is the point, AC7 makes the remaining
wait honest.

Do not add a caching layer to paper over the query cost. A stale board is worse than a slow one for
an app whose whole purpose is telling the owner what changed.
<!-- SECTION:NOTES:END -->
