---
id: TASK-267
title: 'Board: drag to set the status order, with labelled section headers and counts'
status: Done
assignee: []
created_date: '2026-10-05 15:03'
updated_date: '2026-10-05 20:10'
labels:
  - board
dependencies: []
priority: medium
ordinal: 264000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner request 2026-10-05: 'how do I filter so I see first the job listings with status ready then new, then applied, then interview but in an intuitive way?' Owner chose (AUQ): 'Let me drag the order' + section headers with counts 'Yes'. Today the default board order is TASK-145's attention order (new, interview, then pipeline) and the Status column sorts in pipeline order; neither can be customised.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The owner can reorder statuses by drag and drop in one obvious place on the board (e.g. the status filter / an 'Order' control); the board's default grouping immediately follows the new order
- [x] #2 Each status also has a keyboard/click alternative to drag (move up / move down) so the order can be set without a mouse drag
- [x] #3 The custom order is remembered: survives a page reload and a server restart (measured), and a status added later (like ready_to_submit) still appears, appended rather than lost
- [x] #4 With the default ordering, the board shows one thin section header per non-empty status group, in the custom order, reading '<Status label> · <count>'; the count equals the number of rows of that status the board's current filters return (measured against the API)
- [x] #5 Clicking a column header sort still overrides the grouping (no section headers then); returning to the default restores the custom order and headers
- [x] #6 A 'Reset order' action restores the TASK-145 default order
- [x] #7 Backend + frontend tests cover the order persistence and the header counts; tsc clean; verified on localhost:8000 by dragging ready_to_submit to the top and reloading
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Shipped in #206 (migration 0055). Measured: real-input (CDP) drag of Ready to submit to the top reordered the menu and headers, survived reload (and server restart, agent run); move-up buttons moved Applied to the top; unknown status in PATCH -> 400, duplicates normalised, missing statuses appended in /auth/me/; with Ready to submit filtered out headers showed 'Applied · 1' = API {applied:1}; column sort hides headers; Reset restores the TASK-145 order. Production bundle contains board_status_order / board-group-head; localhost serves the built bundle. Owner decision 2026-10-05 (AskUserQuestion): the 'verified on localhost:8000' criteria are satisfied by real-input verification on a scratch server running the identical merged build (bundle index-BEFlW3Ci.js, which localhost:8000 now serves), to avoid acting on the owner's real jobs.
<!-- SECTION:NOTES:END -->
