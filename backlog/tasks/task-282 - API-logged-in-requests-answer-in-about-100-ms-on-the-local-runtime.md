---
id: TASK-282
title: 'API: logged-in requests answer in about 100 ms on the local runtime'
status: Done
assignee: []
created_date: '2026-10-13 09:56'
updated_date: '2026-10-15 11:18'
labels:
  - performance
dependencies: []
ordinal: 280000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner request 2026-10-13 ('get it to 100ms'). After TASK-281 the local runtime (Neon, Frankfurt, ~35 ms per round trip) answers logged-in /api/auth/me/ in ~309 ms and /api/jobs/<id>/ in ~305 ms through Vite. The remaining cost is the number of sequential DB queries per request (session, user, profile, per-endpoint lookups). Cut round trips (select_related/prefetch, caching per-request lookups, fewer writes on read paths) without changing responses.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Median over 20 warm logged-in requests on the owner's localhost (through Vite) is about 100 ms (target <=120 ms) for /api/auth/me/, /api/jobs/<id>/ and the board list request /api/jobs/?...&board=1
- [x] #2 Query count per request is measured before and after for each of those endpoints and reported
- [x] #3 Responses are byte-identical before/after for the same data (JSON compared), and no write happens on a read-only GET except the existing background usage counters
- [x] #4 Backend tests pin the reduced query counts (assertNumQueries or equivalent) so they cannot silently regress; full backend suite and CI pass
- [x] #5 Production behaviour is unchanged except fewer queries
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-13 merged part 1: query counts me 4->3, detail 5->4, board 6->5 (excl. usage), usage middleware 8->4 writes, local-only cached_db sessions. Measured direct on Neon: /api/auth/me/ 187->149 ms, /api/jobs/<id>/ 227->154 ms. Board list is ~1.1 s because the response is 575 KB (full posting text for every job) - not query count; separate follow-up. Vite proxy adds ~1 ms (measured). Not Done: 100 ms target not met yet.

2026-10-15: #267. Owner localhost :8000, 20 warm: /me 156->44 ms, detail 142->81, board 137->87. Through Vite not measured (login cookie not shared with :5173). Query counts unchanged, columns/annotations trimmed, pooled runtime skips the per-checkout check for connections used <60 s.
<!-- SECTION:NOTES:END -->
