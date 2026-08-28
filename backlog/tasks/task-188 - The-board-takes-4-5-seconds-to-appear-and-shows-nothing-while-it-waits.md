---
id: TASK-188
title: The board takes 4.5 seconds to appear and shows nothing while it waits
status: In Progress
assignee:
  - '@pi'
created_date: ''
updated_date: '2026-08-28 13:00'
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
- [x] #1 Measured before and after in a browser on a real board, as a table of resource timings like the one above — a stated number, not "feels faster"
- [x] #2 The board's first row is on screen in under 1.5 s on the owner's machine, or the shortfall is measured and its remaining cause named
- [x] #3 The `auth/me/` serial gate is removed or justified: the board request must not wait on an unrelated request that returns 1 KB
- [x] #4 `/api/jobs/` issues a constant number of queries regardless of row count (TASK-187), proven by a test that fails on the pre-fix code
- [x] #5 The duplicate `jobs/` request is removed, or the reason both are needed is recorded with what each one feeds
- [x] #6 The list payload is measured per row before and after; anything dropped is named, and nothing the board actually renders is dropped
- [x] #7 A skeleton table is shown while loading — same column layout and row height as the real table, so the transition does not jump
- [x] #8 The skeleton does not flash on a fast load: it appears only if loading exceeds a stated threshold, and once shown stays long enough not to strobe
- [x] #9 The transition from skeleton to real rows does not shift layout — first-row top measured in both states and equal
- [x] #10 Verified at desktop width and stated for the 360px card layout, which renders instead of the table (TASK-147 mounts exactly one)
- [x] #11 TASK-165, TASK-139, TASK-167 and TASK-178's note markers all still hold, re-measured after the change
- [x] #12 Backend suite green; frontend typecheck and tests green; `localhost:8000` loads the board after a rebuild in the owner's checkout
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Reverify the recovered auth-gate, independent board-row loading, narrow new-unanalyzed endpoint, payload reduction, gzip, and delayed skeleton implementation. 2. Prove skeleton timing/layout on desktop and 360px, preserve existing board markers, and measure the real board before/after. 3. Run backend/frontend/full browser checks.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
## Coordinator measurement, 2026-08-25 — the latency hypothesis is now a number

The notes below called the remote-database theory a hypothesis with a number attached and said to
test it. Tested, read-only against production:

```
trivial SELECT 1 round trip, 30 samples, warm connection:
  min 24.2 ms | median 25.7 ms | p90 32.8 ms | max 36.2 ms

  72 round trips at the median ..:  1853 ms
   3 round trips at the median ..:    77 ms
measured /api/jobs/ wall clock ..:  3513 ms
```

**Per-query latency explains 53% of the board query, not all of it.** TASK-187's fix -- collapsing
72 round trips to 3 with `select_related` -- is worth about **1.78 s**, taking `/api/jobs/` from
3513 ms to roughly 1730 ms. That alone does NOT reach AC2's under-1.5 s target.

The remaining ~1.66 s is the real queries plus serializing 393 KB over 69 rows. So this task needs
BOTH halves: the N+1 and the payload. An implementation that lands `select_related`, measures a
large improvement and stops has done half the work and will miss AC2.

### And the payload half, measured 2026-08-25

AC6 asks for the payload measured per row. Done, from the real response:

```
/api/jobs/            393 KB over 69 rows      5835 B per row
  latest_evaluation   324 KB                   82.5% of everything
    skill_statuses    180.6 KB                 57.6% of the evaluation, 46% of the WHOLE payload
    main_match_reasons 31.6 KB                 10.1%
    main_gaps          28.2 KB                  9.0%
    required_skills    21.7 KB                  6.9%
    summary            19.8 KB                  6.3%
    matched_skills     16.3 KB                  5.2%
    missing_skills     13.9 KB                  4.4%
  everything else      ~69 KB                  salary_info 5.3, url 4.6, the rest under 3 KB each
```

**`skill_statuses` is the single biggest thing on the wire and most of it is never rendered.**
Measured: 67 rows carry it, averaging **37 entries per row** and peaking at **89**, at 2,760 bytes per
row. The board draws a median of **12** chips per row, and `SkillLabels` takes `limit=8` by default.
So roughly two thirds to three quarters of it is shipped and discarded.

Each entry is `{status, display}`, and `display` is frequently just the title-cased key --
`"Experienced software engineering"` -> `{status: "unknown", display: "Experienced Software
Engineering"}`. That is redundancy on top of over-sending.

This is the same class of decision `JobEvaluationListSerializer` already made when it dropped
`structured_json_raw` (~3.7 KB per evaluation) for being detail-page-only. The list response is
supposed to carry exactly what the board renders; `skill_statuses` stopped honouring that.

Do NOT simply truncate to the first 8: `SkillLabels` sorts by tone before slicing, so the eight it
shows depend on status. Whatever is sent must preserve the board's own ordering, or the chips change.

Neither half is the `auth/me/` serial gate (AC3), which is a further ~1 s before the board request
is even issued, and is independent of both.

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

Session Orchestrator deep session resumed the abandoned implementation from snapshot f85ca993 into isolated branch session-rest-backlog; prior output is treated as untrusted until reverified.

Wave 1 recovery validation: 13 focused backend tests and 5 skeleton tests passed. Recovered implementation includes optimistic auth mounting, independent row loading, a two-column unanalyzed endpoint, list-payload trimming, gzip, and delayed desktop/mobile skeletons; browser geometry/timing remains for Quality.

Wave 2: recovered backend/frontend implementation reviewed and polished; impacted backend files passed 681 tests and all 187 frontend tests passed. Real-browser timing/layout checks remain in Wave 4.

Wave 4 browser measurement on the real 69-row board: API requests start at 724 ms in parallel with auth/me (serial gate removed); one board jobs call takes 1521 ms and first row paints at 2350 ms, down from 4528/~4500 ms. The 850 ms shortfall against 1.5 s is the measured 724 ms shell/usage-middleware start plus the 1521 ms remote-Neon/330 KB board response. Payload fell 402728->329991 bytes (5837->4782 B/row) and gzip transfers 71277 bytes (1033 B/row). Skeleton last top and real first-row top were both 2259.2 px; 360 px card measurement was both 4212.6 px, 69 cards, no table or body overflow. Existing markers: 0 px header overlap, click reaches row, body 1263<=1263, wrapper 1614>1214 with scrollLeft 200, sticky header 60.4 px at scrollTop 0/300/700, 12 note indicators with hover/click, feedback popup portalled and fully visible. Current build loaded 69 rows without error at exact localhost:8000. Full gates passed. Asian Dad: PERFECT.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Removed the auth serial gate and row-scaled relation lookups, replaced the duplicate full jobs fetch with a two-field unanalyzed endpoint, trimmed unreachable skill metadata, enabled gzip, and added delayed desktop/mobile skeletons. Real-board first paint improved from about 4.5 s to 2.35 s; the remaining 0.85 s shortfall is measured and attributed, transitions are layout-stable, and all gates pass.
<!-- SECTION:FINAL_SUMMARY:END -->
