---
id: TASK-309
title: Board selection action bar stays visible while scrolling
status: Done
assignee: []
created_date: '2026-10-18 08:43'
updated_date: '2026-10-18 09:00'
labels:
  - frontend
dependencies: []
priority: medium
ordinal: 310000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner 2026-10-18 screenshot: the '1 selected' bar (Fetch posting text, Edit, Open, Generate CV and Motivation Letter, Archive, status, Analyze, Evaluate, More prompts, Export, Clear) scrolls away when scrolling the job table; it should freeze at the top.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 While rows are selected, the selection bar sticks to the top of the viewport (below the navbar) when the table is scrolled; it stays in normal flow otherwise
- [x] #2 It never covers the table's sticky header or popups (uses the TASK-268 layering scale)
- [x] #3 Works at desktop and phone width without horizontal page scroll
- [x] #4 Verified in the browser by scrolling the board with one row selected; vitest/tsc pass
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Verified 2026-10-18 at 1064px: with PORR selected and scrollY 1795, bar top 37px (below navbar), height 107px, table header visible, no horizontal scroll. Sticky only from md up: on phones the wrapped bar is ~278px.
<!-- SECTION:NOTES:END -->
