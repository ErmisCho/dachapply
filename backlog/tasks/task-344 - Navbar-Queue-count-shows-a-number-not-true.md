---
id: TASK-344
title: 'Navbar Queue count shows a number, not true'
status: Done
assignee: []
created_date: '2026-10-25 14:59'
updated_date: '2026-10-25 15:07'
labels:
  - backend
dependencies: []
priority: high
ordinal: 344000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found 2026-10-25 live while following a new link (job 1936): /api/jobs/application-prep/queue/ returned summary.done = true (total 2). In queue_state the TASK-325 pipeline-row code assigns done = stage == 'skipped', overwriting the TASK-340 done counter, so the navbar shows 'true/2'.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 summary.done is always an integer count, also when a skipped pipeline row is listed
- [x] #2 A test with a skipped pipeline row and a ready document today asserts done == 2
- [x] #3 Live: navbar shows a numeric done/total
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Merged #358. Live after relaunch: queue summary {done: 3, total: 3} (number) with job 1936's skipped row listed; the new test failed on the old code (True == 2).
<!-- SECTION:NOTES:END -->
