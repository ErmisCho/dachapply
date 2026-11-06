---
id: TASK-351
title: Board opens on the next job and applying stays on one bar
status: Done
assignee: []
created_date: '2026-11-06 12:30'
labels:
  - owner-review
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner approved after a measured review: the board's job table starts 1,564 px down and a job page is 4,274 px tall with 16 dropdowns.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 With default panel settings the board shows actionable jobs in the first screen, at 1366x768, with Ready to submit first.
- [x] #2 A job page has a bar that stays visible while scrolling, with Open posting, Copy TeX and Mark applied.
- [x] #3 Each bar action works: Open posting opens the job URL, Copy TeX copies the selected letter, Mark applied sets status applied.
- [x] #4 The stats panels stay reachable and the owner's panel choice is respected.
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Verified in a real browser on disposable data: Next up ended at 295 px, Ready to submit first. The bar stayed in view at every scroll depth. Open posting, Copy TeX (follows the dropdown) and Mark applied all worked. 768 px width not measured.
<!-- SECTION:NOTES:END -->
