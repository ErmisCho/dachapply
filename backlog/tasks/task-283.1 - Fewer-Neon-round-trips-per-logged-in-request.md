---
id: TASK-283.1
title: Fewer Neon round trips per logged-in request
status: In Progress
assignee: []
created_date: '2026-10-13 14:23'
labels:
  - performance
dependencies: []
parent_task_id: TASK-283
ordinal: 283000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Every logged-in request pays ~30 ms per Neon round trip. The board list runs 4 queries (auth_user, profile, jobs, evaluations); the user row and the profile's board columns can come from the session cache instead of the database.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Board list runs at most 2 database queries for a logged-in owner (pinned in test_query_counts)
- [x] #2 Every other pinned endpoint's query count is equal or lower; none rises
- [x] #3 Logout, password change and profile edits take effect on the next request (no stale user or board settings) - covered by tests
- [ ] #4 Full backend suite, vitest and tsc pass
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-13: in-process cache (local runtime only, same gate as cached sessions: DEBUG + DB pool) for the auth user (CachedModelBackend) and the profile's two board columns, evicted by save/delete signals. Azure (2 gunicorn workers) is unchanged. Local counts (excluding usage writes): board_list 4 -> 2, job_detail 3 -> 2, me 2 -> 1; production path unchanged. Each fix falsified. Full backend suite 1475 passed. One-time local re-login after deploy (session backend path changes). Changes made on Azure are seen locally within 60 s.
<!-- SECTION:NOTES:END -->
