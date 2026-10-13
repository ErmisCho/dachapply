---
id: TASK-283
title: 'Board list: fast server response and instant return to the board'
status: In Progress
assignee: []
created_date: '2026-10-13 10:50'
labels:
  - performance
dependencies: []
ordinal: 281000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Measured 2026-10-13 against Neon (TASK-282 follow-up): GET /api/jobs/?...&board=1 returns 575 KB for 111 jobs and takes ~1.1 s, while query count is only 5; the New-only board (63 KB) takes 348 ms. Cost scales with payload: full original_source_text/raw_description and other long text per job. The board rows only need summary fields; the job page loads the detail endpoint.

Re-measured 2026-10-13 on the owner's localhost (111 jobs): the response is gzip'd to 123 KB and downloads in 2 ms; the server spends 1.3-1.7 s before the first byte. cProfile: ~75% of that is skill_matcher.smart_skill_status re-normalising the constant alias tables for every skill of every row (945k regex calls per request). Payload size is not the bottleneck; the analysis text in the payload is read by the board (match/gap popup, skill chip tooltips). Owner also asked (2026-10-13) that returning to the board not wait for a reload.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Board list (/api/jobs/?board=1, owner's 111 jobs, localhost against Neon) median time-to-first-byte over 20 warm requests is under 200 ms
- [x] #2 The board list response body is byte-identical before and after the server change (same hash of the full JSON for the same data)
- [ ] #3 Returning to the board from a job page shows the previous rows immediately (no skeleton, no wait for the request) and then replaces them with the fresh response - verified in the browser
- [x] #4 The cached rows are never shown to a different account: cache is keyed by user and cleared on logout
- [x] #5 Query counts stay pinned (TASK-282 tests) and the full backend suite, frontend tests and tsc pass
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-13, measured on the owner's 111 jobs (TTFB, 20 warm requests, localhost against Neon): ~1.3-1.7 s -> median 486 ms; response hash identical before/after (abed2f1ecc0b4).
- skill_matcher: alias norms precomputed, smart_skill_status/display_skill_name cached (was ~75% of the request).
- Board list loads only the columns its serializers read: no full postings, no raw LLM replies, has_pending_source answered in SQL, profile reduced to the two board columns (~1.8 MB -> ~0.3 MB from Neon per request).
- Frontend: last board rows kept in memory per user+query, painted on return while the list revalidates; cleared by clearAuthCache (logout/login/401).
- AC#1 (<200 ms) NOT met: what remains is 4 Neon round trips (~30 ms each) plus the analysis text the board's popups and skill tooltips read, and ~150 ms of Python. Owner chose to ship this and keep the task open for the target.
- AC#3 to be verified in the browser on the relaunched localhost.
<!-- SECTION:NOTES:END -->
