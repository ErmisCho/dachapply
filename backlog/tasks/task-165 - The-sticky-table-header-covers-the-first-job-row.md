---
id: TASK-165
title: The sticky table header covers the first job row
status: To Do
assignee: []
labels:
  - frontend
  - bug
  - ux
dependencies: []
priority: high
ordinal: 165000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner report, 2026-08-21: *"the first job listing is always neither visible nor clickable."*

Reproduced and measured in a browser against the board, not inferred from the CSS:

    .job-table thead th   position: sticky; top: 32.8px (2.05rem); z-index: 12
    sticky header bottom  y = 813
    first row top         y = 780
    OVERLAP               33 px   (== the top offset, exactly)
    first row height      78 px   -> 42% of the row is covered

It is worse than a cosmetic clip. The first row's link occupies y 784-804, entirely above the
header's bottom edge at 813, so `document.elementFromPoint()` at that link returns:

    BUTTON  (a header sort control)   isHeader: true, inRow1: false

Clicks aimed at the first job land on the table header instead. The same probe one row lower returns
an element inside row 2, which is why every other row behaves normally and only the first is affected.

**The offset is not gratuitous**, which is why the obvious fix is wrong. Setting `top: 0` measures a
clean 0 px overlap — but the 2.05rem exists to clear `.app-nav`, which is `position: sticky; top: 0`
with a measured height of **37 px** and `z-index: 20` against the table header's `z-index: 12`. So
`top: 0` would slide the header under the nav and hide the header instead of the row. Note also that
32.8px is already less than the nav's 37px, so the current value does not even fully clear what it
was chosen to clear — whatever fix is chosen should derive the offset from the nav's real height
rather than restating a magic number.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The first body row of the job table is fully visible: measured overlap between the sticky header's bottom and the first row's top is 0 px, at the top of the page and while scrolled
- [ ] #2 A click aimed at the first row's link reaches that link — `elementFromPoint` at its centre returns an element inside the first row, not a header control — verified in a browser, since this is exactly what reading the CSS failed to reveal
- [ ] #3 The table header is still not covered by `.app-nav`: the header remains fully visible while scrolled, verified by measurement rather than by screenshot impression
- [ ] #4 The offset is derived from the nav's actual height rather than a hardcoded rem value that can drift out of step with it, or the notes state why a constant is unavoidable and how it stays in sync
- [ ] #5 Verified at desktop width and at 360 px, since the nav's height changes with breakpoint and a fix tuned to one width can reintroduce the overlap at the other
- [ ] #6 No regression to the horizontal scrolling of the table wrapper, which TASK-139 already had to fix once after a CSS override forced both axes to `visible`
- [ ] #7 Frontend typecheck and tests green
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Measurement technique that found this, worth reusing: compare `thead th` and first `tbody tr`
bounding rects for overlap, then probe `document.elementFromPoint()` at the row's own link position
and assert the returned node is inside that row. Reading `position: sticky` in the stylesheet looks
entirely correct and reveals nothing — the defect only appears when the two boxes are measured
against each other.
<!-- SECTION:NOTES:END -->
