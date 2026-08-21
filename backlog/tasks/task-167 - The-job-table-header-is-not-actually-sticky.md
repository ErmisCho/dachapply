---
id: TASK-167
title: The job table header is not actually sticky
status: To Do
assignee: []
labels:
  - frontend
  - ux
dependencies:
  - TASK-165
priority: low
ordinal: 167000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found 2026-08-21 while fixing TASK-165, and split out rather than folded in because it is a different
change with a different risk.

`.job-table thead th` carries `position: sticky`, and has since it was written, but the header has
never actually stayed visible while scrolling the page. Measured, page scroll, thead top:

    8373  ->  -20  ->  -420

It scrolls away with the table like any static element.

**Why.** `position: sticky` resolves against the nearest scrollable ancestor, which here is the
table's `.overflow-x-auto` wrapper. That wrapper's `overflow-y` COMPUTES to `auto` even though it is
written to only scroll horizontally, because CSS forces `visible` to `auto` on one axis when the
other axis is not `visible`. So the wrapper is a scroll container on both axes, and the header sticks
to it rather than to the page.

TASK-165 removed the harm this caused (a `top` offset that only pushed the header down over the first
row, hiding 42% of it and stealing its clicks) by setting `top: 0`. It deliberately did NOT try to
make the header genuinely sticky, because that means removing or restructuring the scroll container —
which is exactly the tension TASK-139 already had to resolve once, when a CSS override forced both
axes to `visible` and broke horizontal scrolling while trying to stop vertical clipping.

So this is optional polish, not a defect: the table reads fine without a pinned header, and the
column labels are re-readable by scrolling up. It is filed so the `position: sticky` in the
stylesheet is not mistaken for working behaviour by the next person who reads it.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The column header row remains visible while scrolling the board vertically past the first screen of rows, verified by measuring the thead's viewport position at three scroll offsets rather than by screenshot
- [ ] #2 The header sits below `.app-nav` rather than under it, measured — the nav is sticky at top:0 with z-index 20 against the header's 12, so a header pinned at top:0 would be covered
- [ ] #3 Horizontal scrolling of the wide table still works: the wrapper's scrollWidth exceeds its clientWidth at a width where the table is wider than the viewport, and the document itself does NOT scroll horizontally — this is TASK-139's exact regression and must be re-measured, not assumed
- [ ] #4 Row popups and overlays are still not clipped vertically, which is the reason the wrapper was split in two in the first place
- [ ] #5 The first body row is still fully visible and clickable — TASK-165's fix must not be undone by whatever makes the header sticky
- [ ] #6 Verified at desktop width and at the narrowest width where the job table renders (measured 2026-08-21 as ~1037 px; below that the board switches to a card layout and has no table)
- [ ] #7 Frontend typecheck and tests green
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
The likely shape is to stop relying on an ancestor being non-scrolling: either give the table its own
vertical scroll container with a bounded height (so sticky resolves against something that genuinely
scrolls vertically), or remove the horizontal wrapper and let the table scroll the page, which
reopens TASK-139. Measure before choosing; TASK-165's whole lesson was that the obvious fix and the
correct fix were opposites.
<!-- SECTION:NOTES:END -->
