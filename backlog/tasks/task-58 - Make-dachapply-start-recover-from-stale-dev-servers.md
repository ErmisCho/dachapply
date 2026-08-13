---
id: TASK-58
title: Make dachapply start recover from stale dev servers
status: Done
assignee:
  - '@pi'
created_date: '2026-08-13 08:51'
updated_date: '2026-08-13 08:53'
labels:
  - bug
  - dev-experience
dependencies: []
modified_files:
  - ../Configuration/bin/dachapply-start.cmd
  - ../Configuration/test.cmd
priority: medium
ordinal: 59000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The Windows project launcher starts Django before Vite, but a stale Vite listener on port 5173 makes the new frontend exit and can leave the newly started Django process behind. Make repeated startup deterministic without changing the fixed development ports.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Running dachapply start when ports 5173 or 8000 have stale listeners starts fresh Django and Vite servers on the configured ports without a port-in-use error
- [x] #2 The launcher smoke check verifies both development ports are handled
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Clear existing listeners on the two fixed dev ports before launching. 2. Extend the existing launcher smoke check to lock in both ports. 3. Reproduce startup with occupied ports and verify fresh listeners respond.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Updated the Windows launcher to terminate listeners on ports 5173 and 8000 before starting fresh servers. Added a launcher smoke assertion. Verified against the reported live stale processes: PIDs 31016/37424 were replaced by 76212/68896 and both endpoints returned HTTP 200 with no Vite port error.

Validation passed: Configuration/test.cmd reported all checks green; occupied-port integration restarted both servers, received HTTP 200 from ports 5173 and 8000, and left both ports clean afterward.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Made dachapply start clear stale listeners on its fixed frontend and backend ports before launch, preventing repeat-start collisions. Added a smoke assertion and verified fresh servers replaced the reported stale processes and served HTTP 200.
<!-- SECTION:FINAL_SUMMARY:END -->
