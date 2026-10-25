---
id: TASK-344
title: 'Navbar Queue count shows a number, not true'
status: To Do
assignee: []
created_date: '2026-10-25 14:59'
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
- [ ] #1 summary.done is always an integer count, also when a skipped pipeline row is listed
- [ ] #2 A test with a skipped pipeline row and a ready document today asserts done == 2
- [ ] #3 Live: navbar shows a numeric done/total
<!-- AC:END -->
