---
id: TASK-315
title: Board table columns can be reordered by drag and drop
status: In Progress
assignee: []
created_date: '2026-10-19 16:19'
updated_date: '2026-10-19 16:55'
labels:
  - frontend
dependencies: []
priority: medium
ordinal: 315000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner 2026-10-19: 'maybe through the statuses drag and drop window of statuses, I can rearrange the columns. give me that option'. Status order is already draggable (Status list, saved to the account, TASK-267). The board's Columns picker can only show/hide columns. Owner chose: same drag-and-drop for the table columns, kept in this browser for now (account storage needs a migration + Azure deploy -> TASK-316).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The board's Columns picker lets the owner drag a column to a new position, with the same drag handle and drop outline as the Status list; keyboard users can move a column up/down with buttons
- [x] #2 The desktop board table renders its reorderable columns (header and every row cell) in the chosen order; hidden columns stay hidden; columns outside the picker (selection, actions) keep their place
- [x] #3 The order is saved in this browser (localStorage key next to dachapply_hidden_cols), survives reload, and a Reset restores the default order; an unknown or missing key in a saved order falls back safely (new columns appended)
- [ ] #4 The mobile card list is unaffected or follows the same order, with no layout break at phone width
- [x] #5 Tests cover reorder, persistence/fallback and the rendered header order, each failing when its logic is removed; vitest and tsc pass
- [x] #6 Verified on localhost: dragging a column in the picker moves it in the table and the order survives a reload
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Verified on localhost 2026-10-19 (PR #301): drag (DragEvents) moved Skills before Position in header and rows, order survived reload, arrow button and Reset order work. AC4 (phone width) checked by code only: mobile cards untouched; not screen-verified, to avoid resizing the owner's browser window.
<!-- SECTION:NOTES:END -->
