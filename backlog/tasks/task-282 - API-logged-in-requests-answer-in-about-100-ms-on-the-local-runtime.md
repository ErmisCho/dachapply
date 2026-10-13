---
id: TASK-282
title: 'API: logged-in requests answer in about 100 ms on the local runtime'
status: In Progress
assignee: []
created_date: '2026-10-13 09:56'
updated_date: '2026-10-13 10:12'
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
- [ ] #1 Median over 20 warm logged-in requests on the owner's localhost (through Vite) is about 100 ms (target <=120 ms) for /api/auth/me/, /api/jobs/<id>/ and the board list request /api/jobs/?...&board=1
- [ ] #2 Query count per request is measured before and after for each of those endpoints and reported
- [ ] #3 Responses are byte-identical before/after for the same data (JSON compared), and no write happens on a read-only GET except the existing background usage counters
- [ ] #4 Backend tests pin the reduced query counts (assertNumQueries or equivalent) so they cannot silently regress; full backend suite and CI pass
- [ ] #5 Production behaviour is unchanged except fewer queries
<!-- AC:END -->
