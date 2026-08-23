---
id: TASK-178
title: Hide notes behind a click on the board
status: To Do
assignee: []
labels:
  - frontend
  - ux
dependencies: []
priority: medium
ordinal: 178000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner, 2026-08-23: *"the notes should be hidden by default and shown only when clicked on."*

Notes currently render inline in the job table. They are reference material consulted occasionally,
not a column scanned every time the board is opened, and on a row-dense board they cost vertical
space on every row whether or not the owner is reading them.

This is the same judgement the owner made about the unmatched-mail panel in TASK-174 — a thing that
is useful on demand should not be permanently resident on the screen used for daily decisions. Both
requests share a shape worth stating once: the board is for today's decisions, and anything else
earns its place by being asked for.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Notes are not rendered inline by default; a row shows an affordance indicating a note exists rather than the note's text
- [ ] #2 A row with NO note is visually distinguishable from a row with an unread note — the affordance must not appear on rows that have nothing behind it
- [ ] #3 Clicking reveals the note without leaving the board and without a page navigation
- [ ] #4 Editing a note still works from the revealed state, with no loss of any editing capability that exists today
- [ ] #5 Measured: board table height and per-row height before and after, on a stated number of rows, so the space actually reclaimed is a number rather than an impression
- [ ] #6 Verified at desktop width and at 360px, where the board renders a card layout rather than a table
- [ ] #7 The first row stays fully visible and clickable (TASK-165) and the table still scrolls horizontally (TASK-139), both re-measured
- [ ] #8 Frontend typecheck and tests green; `localhost:8000` loads the board without an application error after a rebuild in the owner's checkout
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
The board already has a row-level popup pattern (the feedback editor) and it is the wrong one to copy
verbatim: TASK-173 exists precisely because that popup is a non-portalled absolutely-positioned child
of the table's scroll wrapper, which is what blocks TASK-167. If notes need a popup, portal it, or
land TASK-173 first and follow whatever pattern that establishes. Do not add a second popup with the
same clipping problem.

AC2 matters more than it looks. Hiding the text is only an improvement if the owner can still see
WHICH jobs have notes — otherwise the feature becomes invisible rather than tidy, and they have to
click every row to find out.
<!-- SECTION:NOTES:END -->
