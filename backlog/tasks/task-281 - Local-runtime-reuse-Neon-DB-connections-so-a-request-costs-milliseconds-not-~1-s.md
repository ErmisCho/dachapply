---
id: TASK-281
title: >-
  Local runtime: reuse Neon DB connections so a request costs milliseconds, not
  ~1 s
status: In Progress
assignee: []
created_date: '2026-10-13 08:57'
labels:
  - performance
dependencies: []
ordinal: 276000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner chose (2026-10-13) to investigate why every localhost request takes ~1 s. Measured: GET /api/auth/me/ direct to Django 127.0.0.1:8000 = 0.56-0.68 s even for a 403; via Vite 0.6-1.9 s; TCP connect to the Neon pooler 45 ms but intermittently 1.05 s (DNS returns IPv6 first). Cause: runserver serves each request on a new thread, so CONN_MAX_AGE persistent connections never get reused and every request opens a new TLS connection to Neon (Frankfurt). Django 5.2 + psycopg 3.3 support a native connection pool (OPTIONS pool) via psycopg[pool], which persists across threads.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 With the local runtime (runserver against the Neon DATABASE_URL), GET /api/auth/me/ direct to 127.0.0.1:8000 has a median under 150 ms over 20 warm requests (before: ~600 ms)
- [ ] #2 Connections come from Django's native psycopg pool (OPTIONS pool) with persistent connections disabled as Django requires; psycopg[pool] is added to the locked dependencies
- [ ] #3 The pool is on for the local DEBUG runtime; production behaviour is unchanged unless explicitly enabled by an env var
- [ ] #4 Dropped/idle connections (Neon closes idle ones) do not surface as request errors: a request after 10+ minutes idle succeeds
- [ ] #5 Backend tests (sqlite) and CI pass; the Vite proxy target uses 127.0.0.1 instead of localhost so it never waits on an IPv6 attempt
<!-- AC:END -->
