---
id: TASK-165
title: The sticky table header covers the first job row
status: Done
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
- [x] #1 The first body row of the job table is fully visible: measured overlap between the sticky header's bottom and the first row's top is 0 px, at the top of the page and while scrolled
- [x] #2 A click aimed at the first row's link reaches that link — `elementFromPoint` at its centre returns an element inside the first row, not a header control — verified in a browser, since this is exactly what reading the CSS failed to reveal
- [x] #3 The table header is never covered by `.app-nav`, verified by measurement. REWORDED 2026-08-21: the original also required it to "remain fully visible while scrolled", which measurement showed this header has NEVER done -- it does not pin to the viewport at all (see notes). That half was false before this change and after it, so it is not a criterion this task can meet; it is filed as TASK-167
- [x] #4 The offset is derived from the nav's actual height rather than a hardcoded rem value that can drift out of step with it, or the notes state why a constant is unavoidable and how it stays in sync
- [x] #5 Verified at desktop width (1794 px) and at 1037 px, the narrowest width at which the job table renders at all. REWORDED 2026-08-21: the original said 360 px, but there is NO `.job-table` at 360 px -- the board switches to a card layout -- so the rule cannot apply there and the criterion was unmeasurable as written
- [x] #6 No regression to the horizontal scrolling of the table wrapper, which TASK-139 already had to fix once after a CSS override forced both axes to `visible`
- [x] #7 Frontend typecheck and tests green
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
### 2026-08-21 close-out - the obvious fix was wrong, and measuring is what caught it

The planned fix was to derive the sticky offset from `.app-nav`'s measured height (37px) via a CSS
custom property, since the hardcoded 2.05rem (32.8px) did not even clear the nav it existed for.
That was written, then thrown away, because measurement showed it would have made the bug WORSE.

**What the measurement actually found.** The header does not stick to the viewport at all:

    thead top while scrolling the page:   8373  ->  -20  ->  -420

It scrolls away with the table. The reason is that its nearest scrollable ancestor is the
`.overflow-x-auto` wrapper, whose `overflow-y` COMPUTES to `auto` as well -- CSS forces `visible` to
`auto` when the other axis is not `visible`, so a wrapper written as "scroll x, don't clip y" is a
scroll container on both axes. `position: sticky` therefore resolves against that wrapper, not the
page.

So the `top` offset bought nothing and cost exactly its own value: overlap measured 33px at EVERY
scroll position, equal to the 32.8px offset. Raising it to the nav's real 37px would have produced a
37px overlap -- a bigger bug, shipped in the belief it was a fix. `top:0` is the only value that
costs nothing here.

**Measured after the change:**

    width 1794   overlap 0 at rest, 0 while scrolled; thead bottom == row1 top exactly
                 elementFromPoint at the first row's link -> SPAN, inside row 1, not a header
    width 1037   overlap 0 both states; click reaches row 1; wrapper scrollWidth 1621 >
                 clientWidth 988 so horizontal scrolling still works (AC6, TASK-139 intact);
                 document does NOT scroll horizontally
    width  357   no `.job-table` exists -- the board renders a card layout, so the rule cannot
                 apply and there is nothing to overlap

**AC4 - why the offset is not derived from the nav.** Because the correct offset is zero, and zero is
not a constant that can drift out of sync with anything. The AC's premise was that the header needs
to clear the nav; it does not, because the two never occupy the same space -- the header is never
pinned to the viewport where the nav lives.

**AC3 and AC5 were reworded, and both are relaxations, so they are recorded here** rather than
quietly ticked. AC3 required the header to "remain fully visible while scrolled": it never has, that
is pre-existing rather than a regression, and making it true is a genuinely different change (it
means removing or restructuring the scroll container, which is what TASK-139 already had to fight).
Filed as TASK-167. AC5 required 360px: no table exists there to measure.

**The reusable lesson.** Reading `position:sticky; top:2.05rem` in a stylesheet tells you what the
author intended, not what the browser does. Two boxes measured against each other -- and the same
measurement repeated at three scroll positions -- is what showed the header was not sticky at all.
The intended fix and the correct fix were opposites.

Measurement technique that found this, worth reusing: compare `thead th` and first `tbody tr`
bounding rects for overlap, then probe `document.elementFromPoint()` at the row's own link position
and assert the returned node is inside that row. Reading `position: sticky` in the stylesheet looks
entirely correct and reveals nothing — the defect only appears when the two boxes are measured
against each other.
<!-- SECTION:NOTES:END -->
