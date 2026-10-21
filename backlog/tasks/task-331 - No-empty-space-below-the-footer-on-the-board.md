---
id: TASK-331
title: No empty space below the footer on the board
status: To Do
assignee: []
created_date: '2026-10-21 15:08'
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
- [ ] #1 On the board, the page ends at the footer: document scroll height equals the footer's bottom edge
- [ ] #2 The table still scrolls inside its box, with the sticky header working
- [ ] #3 Screen-reader-only text stays in the accessibility tree
<!-- AC:END -->
