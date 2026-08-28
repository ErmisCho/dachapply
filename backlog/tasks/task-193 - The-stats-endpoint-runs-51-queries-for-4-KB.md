---
id: TASK-193
title: The stats endpoint runs 51 queries for 4 KB
status: In Progress
assignee:
  - '@pi'
created_date: ''
updated_date: '2026-08-28 13:00'
labels:
  - backend
  - performance
dependencies:
  - TASK-188
priority: medium
ordinal: 193000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found on 2026-08-25 by the agent implementing TASK-188, and reported rather than folded into an
unrelated diff — the same call TASK-178's agent made when it found TASK-187.

`/api/stats/` issues **51 queries** and takes **2008 ms** to return **4 KB**, of which roughly 46 are
correlated subqueries. Coordinator re-measured it in a browser on the owner's board: **3050 ms** on a
cold load, **2008 ms** warm.

**It is no longer on the board's critical path.** Before TASK-188, `load()` awaited `Promise.all` of
every request, so `stats/` decided when rows painted. Rows are now awaited alone, which is why the
board reaches 1852 ms while `stats/` is still running. So this is no longer urgent — but it is now the
**largest remaining server cost on the page**, and the panels it feeds (funnel, conversion, upcoming
interviews) stay empty for two seconds after the board is usable.

Context that changes the arithmetic: the database is remote Neon, where a trivial `SELECT 1` round
trip is **25.7 ms** median over 30 warm samples. 51 round trips is 1310 ms of pure latency before any
query does work. That is a hypothesis with a number attached, not a conclusion — the equivalent
reasoning was wrong for TASK-187, where the measured saving was larger than latency alone predicted
(2953 ms → 654 ms against a predicted ~1730 ms), because each query cost more than a bare round trip.
Measure before choosing a fix.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Query count and wall clock measured before and after, as numbers, in a browser on a real board
- [x] #2 The query count no longer scales with the number of jobs, proven by a test that fails on the pre-fix code
- [x] #3 Every figure the endpoint returns is unchanged for the owner's real data — compared field by field before and after, since these feed the funnel and conversion panels
- [x] #4 TASK-184's ownership scoping is unchanged: the same rows are counted, only fetched differently
- [x] #5 No caching layer — a stale funnel is worse than a slow one, the same rule TASK-188 was held to
- [x] #6 Backend suite green
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Capture and group the stats endpoint queries and full response. 2. Replace row-scaling query patterns with bounded aggregate work while preserving every field and owner scope, without caching. 3. Prove constant query count, compare real response field-by-field, measure browser wall clock, and run the backend suite.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Do not start by rewriting. Start by printing the 51 queries with `connection.queries` and grouping
them — the shape of the fix depends entirely on whether they are 46 near-identical correlated
subqueries (one aggregate pass replaces them) or 46 genuinely different questions (they need
batching, not merging).

AC3 is the one most likely to be quietly failed. `source_effectiveness`, the funnel and the
per-status counts are all derived numbers; an aggregate rewrite that changes a denominator silently
changes what the owner reads off the dashboard. Capture the full JSON response before the change and
diff it after.

Worth noting while here, though it belongs to nobody yet: `scripts/start-container.sh` runs gunicorn
with `WEB_CONCURRENCY:-2`, so the page's six parallel requests queue against two sync workers. That
inflates every browser-side number on this page and is infrastructure rather than code — the owner's
call, and it should not be fixed by pretending it is a query problem.

Wave 3 premise correction, measured before implementation against production: /api/stats/ issued 65 queries in 2657.0 ms for 4638 bytes; 48 queries hit jobradar_joblead. Query count was already independent of job count—the actual scaling axis is one SQL count per weekly/month-week/workday bucket. Asian Dad criterion 2 was formally superseded before implementation: target <=10 queries independent of both job count and month length, with the current 65-query implementation as the failing pre-fix case.

Wave 3 premise correction, measured before implementation against production: /api/stats/ issued 65 queries in 2657.0 ms for 4638 bytes; 48 queries hit jobradar_joblead. Query count was already independent of job count—the actual scaling axis is one SQL count per weekly/month-week/workday bucket. Asian Dad criterion 2 was formally superseded before implementation: target <=10 queries independent of both job count and month length, with the current 65-query implementation as the failing pre-fix case.

Cap refinement before implementation: the same capture showed 14 fixed auth/usage-middleware queries outside the stats view. The objective is therefore <=10 stats-owned job/evaluation/follow-up queries, not an impossible <=10 whole-request total.

Wave 3 implementation: one application-row fetch now supplies all time buckets, funnel counts and source effectiveness; fixed job/evaluation aggregates replace repeated counts. Production remeasurement: 20 total queries, 6 stats-owned queries, 1069.3 ms, 4638 bytes, versus 65 total/48 JobLead queries, 2657.0 ms, 4638 bytes. Deep comparison of the complete owner response is exactly equal. No cache was added and the owned-jobs queryset is unchanged.

Wave 4 browser post-fix stats timing was 1169.5 ms on the owner board versus 3050 ms cold/2008 ms warm before. In-process production capture remained 20 total/6 stats-owned queries versus 65/48, with exact 4638-byte deep response parity. Constant-query regression, owner scoping, no-cache inspection, and all 1014 backend tests passed. Asian Dad: PERFECT (self-graded disclosure applies).
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Replaced per-bucket SQL counts with one scoped application-row pass and fixed aggregates. Stats-owned queries fell from 48 to 6, browser latency improved, the complete production response remained byte-for-byte equivalent after canonical serialization, and no cache was added.
<!-- SECTION:FINAL_SUMMARY:END -->
