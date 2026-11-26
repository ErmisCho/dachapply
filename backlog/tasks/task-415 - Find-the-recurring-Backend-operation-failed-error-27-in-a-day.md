---
id: TASK-415
title: Find the recurring 'Backend operation failed' error (27 in a day)
status: In Progress
assignee: []
created_date: '2026-11-25 12:34'
updated_date: '2026-11-26 11:30'
labels: []
dependencies: []
priority: medium
ordinal: 419000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The error collector holds 27 occurrences of one backend error group (operation 39ec6ac5...) from 2026-11-24 09:45 to 2026-11-25 09:57 UTC, with no traceback. One of them was an HTTP 500 on DELETE /api/jobs/2104/ that returned the expected 400 on retry. Find the cause from the occurrence data and server logs, fix it with a test.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The cause is named with the evidence that shows it
- [x] #2 A test reproduces it red, then green on the fix
- [ ] #3 After the fix, no new occurrence of that group for one day of normal use (checked from the collector)
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-25: the 27 occurrences are logger django.request (HTTP 500s), in bursts after idle gaps. No exception type or route was kept, so the cause is unknown. PR #460 (64ea209) now keeps '<exception class>@<view name>' for each 500; localhost runs it. Next: read the next occurrences from the collector and fix the named cause.

2026-11-26: PR #460 named the group: OperationalError@jobradar.views_application_prep.application_prep_queue (10:13 UTC today, after an idle gap). Likely cause: the pool's 10 s wait for a connection ran out while Neon woke up. PR #465 (826606e) raises the pool timeout to 30 s and records the root of the exception chain (e.g. PoolTimeout), with two tests red on main and green on the fix; localhost runs it. AC1 stays open until an occurrence names the root, or a quiet day (AC3) supports the pool-wait cause. Check the collector after 2026-11-27 11:30.
<!-- SECTION:NOTES:END -->
