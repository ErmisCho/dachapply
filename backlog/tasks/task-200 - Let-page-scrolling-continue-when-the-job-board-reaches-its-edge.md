---
id: TASK-200
title: Let page scrolling continue when the job board reaches its edge
status: To Do
assignee:
  - '@pi'
created_date: '2026-08-29 21:25'
labels:
  - frontend
  - bug
  - accessibility
dependencies: []
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
- [ ] #1 While the job board can still move in the requested direction, wheel or touchpad input scrolls the job board rather than the page
- [ ] #2 When the job board is at its bottom edge, continuing to scroll downward moves the main page without requiring a second gesture or moving the pointer
- [ ] #3 When the job board is at its top edge, continuing to scroll upward moves the main page without requiring a second gesture or moving the pointer
- [ ] #4 The behavior works on the home-page job board without breaking its independent scrollbar
- [ ] #5 A browser regression check covers scroll chaining at both board edges
<!-- AC:END -->
