---
id: TASK-200
title: Let page scrolling continue when the job board reaches its edge
status: Done
assignee:
  - '@pi'
created_date: '2026-08-29 21:25'
updated_date: '2026-08-30 07:03'
labels:
  - frontend
  - bug
  - accessibility
dependencies: []
modified_files:
  - frontend/src/App.tsx
  - frontend/src/boardScrollChaining.test.tsx
  - .orchestrator/debug/task-200-2026-08-29-bugfix-1-1.md
priority: medium
type: bug
ordinal: 200000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The home-page job board has its own vertical scrollbar. While the pointer is over it, reaching the board's top or bottom traps the next scroll input, so the user must scroll again or move the pointer outside the board before the main page moves. Preserve nested board scrolling, but hand further movement in the already-exhausted direction to the page immediately.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 While the job board can still move in the requested direction, wheel or touchpad input scrolls the job board rather than the page
- [x] #2 When the job board is at its bottom edge, continuing to scroll downward moves the main page without requiring a second gesture or moving the pointer
- [x] #3 When the job board is at its top edge, continuing to scroll upward moves the main page without requiring a second gesture or moving the pointer
- [x] #4 The behavior works on the home-page job board without breaking its independent scrollbar
- [x] #5 A browser regression check covers scroll chaining at both board edges
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Reproduce the lost wheel delta at the bounded desktop job board and record the root cause. 2. Split an edge-crossing wheel delta between the board's remaining scroll range and the page, using one non-passive listener on the existing board wrapper. 3. Add focused delta-splitting tests for middle, bottom, top, and edge-crossing cases. 4. Measure board/page deltas in a real headless Chrome session, then run full frontend/backend gates. 5. Merge, update both local and Azure releases, close TASK-200, and finalize.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Root-cause measurement on released main: with the board 50 px from its bottom, one 180 px wheel input moved the board 50 px, the page 0 px, and lost the remaining 130 px. The wrapper has only native overflow-y:auto and no wheel handoff; Chrome consumes the edge-crossing input in the nested scroller, so page movement waits for another input. A discrete input beginning at the exact edge does chain natively, which is why the fix must handle the crossing remainder rather than disable independent board scrolling.

Implemented one native non-passive wheel listener on the existing desktop board wrapper. Fully consumable input remains native board scrolling; an edge-crossing input is split into the board's remaining distance and an immediate page scroll remainder. Mobile remains page-scrolled because the listener is disabled below the existing 1024 px breakpoint.

Validation: focused delta tests passed; real headless Chrome measured board/page deltas of middle 180/0, bottom crossing 50/130, bottom 0/180, top crossing -30/-150, and top 0/-180 with the pointer remaining over the board. Full gates passed: 1027 backend tests, 195 frontend tests, production build, npm audit with zero vulnerabilities, and diff check.

PR #99 squash-merged as e1a780a55406064ec4e71d0222ba91c4184fa6cd. Main CI, GitGuardian, Azure deployment, and public-app verification passed in run 33298090010. The synchronized local runtime serves the same SHA with HTTP 200 on ports 8000 and 5173.

Asian Dad evaluation: PERFECT (self-graded). All six sealed criteria passed using real Chrome board/page delta measurements, focused tests, full frontend/backend gates, and successful main deployment evidence.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Preserved independent desktop job-board scrolling while transferring any unconsumed top/bottom wheel remainder to the page on the same input. Verified in Chrome with exact board/page deltas for middle, crossing, and edge cases in both directions; 1027 backend tests, 195 frontend tests, production build, CI, and Azure deployment passed.
<!-- SECTION:FINAL_SUMMARY:END -->
