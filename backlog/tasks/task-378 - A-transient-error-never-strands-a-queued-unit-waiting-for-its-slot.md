---
id: TASK-378
title: A transient error never strands a queued unit waiting for its slot
status: Done
assignee: []
created_date: '2026-11-13 20:30'
labels: []
dependencies: []
priority: high
type: bug
ordinal: 380000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Observed 2026-11-13 on the local runtime: four pipeline units queued on 2026-11-12 07:26 UTC stayed queued for ~37 h while later analyses ran; status showed 0 running, 4 remaining. processing_control.execute() polls control.claim() with no error handling, and the unit's limit function reads the profile from the database, so one transient error kills the waiting thread and the unit is never claimed until the runtime restarts. A runtime restart re-dispatched them immediately.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 An exception while waiting to claim (claim or the limit function) does not end the waiting worker; it retries with a short backoff and logs the error once per unit.
- [x] #2 Regression test injects one transient failure in the limit and proves the unit is still claimed and run; it fails on the current code.
- [x] #3 A persistent error does not spin hot (backoff) and the unit stays recoverable by a restart.
- [x] #4 Existing processing-control tests stay green.
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-13 (coordinator): execute() now retries the claim wait on any exception (1 s backoff, logged once per unit). Regression test fails on main (thread dies, unit queued) and passes here; test_processing_control 11 passed. The stuck runtime units were released by a runtime restart (update to 7333486): status went from 0 running / 4 waiting to 1 running / 3 waiting.
<!-- SECTION:NOTES:END -->
