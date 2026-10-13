---
id: TASK-285
title: Interview jobs in their own toggleable table on the board
status: In Progress
assignee: []
created_date: '2026-10-13 14:37'
labels:
  - board
  - frontend
dependencies: []
ordinal: 285000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner 2026-10-13: jobs in status 'interview' should sit in their own table on the board, which can be toggled, with the same columns as the main table.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Board shows a separate 'Interviews' table holding every job in status interview that the board's filters allow
- [x] #2 It renders the same columns as the main table, honours the same column visibility settings and row actions (edit, status change, notes, select)
- [x] #3 A toggle shows/hides it; the choice survives a reload. Shown: interview jobs appear only there, not also in the main table. Hidden: they return to the main table as today
- [ ] #4 Desktop and mobile layouts both work; verified in the browser on the owner's data
- [ ] #5 vitest, tsc and backend suite pass
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-13, verified in the browser on the owner's data (desktop): Interviews table holds exactly the 5 interview jobs, main table the other 106 with none duplicated; headers identical, also after hiding Skills; toggle off puts all 111 back in the main table and survives a reload; a status change from the Interviews table sends the right PATCH (intercepted, nothing persisted) and the row leaves the table.
Not yet verified: phone width (browser automation could not shrink the viewport). Known limit: shift-click range selection across the two tables follows the full list order.
<!-- SECTION:NOTES:END -->
