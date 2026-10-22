---
id: TASK-331
title: No empty space below the footer on the board
status: Done
assignee: []
created_date: '2026-10-21 15:08'
updated_date: '2026-10-22 13:26'
labels:
  - frontend
dependencies: []
priority: medium
ordinal: 331000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner 2026-10-21 (screenshot): 'under the last table there should be the footer and that's it, not have empty space underneath'. Measured on localhost: html ends at the footer (3,081 px) but the document scrolls to 9,103 px. The cause is position:absolute .sr-only spans inside table rows: their containing block is the premium-card (relative), outside .job-table-scroll, so they escape the scroller's clip and stretch the page to the hidden last row.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 On the board, the page ends at the footer: document scroll height equals the footer's bottom edge
- [x] #2 The table still scrolls inside its box, with the sticky header working
- [x] #3 Screen-reader-only text stays in the accessibility tree
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Merged #329. Live: board document height 3,897 px = footer bottom 3,897 px; sticky header offset 0; sr-only spans present.
<!-- SECTION:NOTES:END -->
