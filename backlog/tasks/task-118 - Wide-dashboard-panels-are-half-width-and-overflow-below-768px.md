---
id: TASK-118
title: Wide dashboard panels are half-width and overflow below 768px
status: To Do
assignee: []
labels:
  - frontend
  - responsive
  - bug
dependencies: []
priority: medium
ordinal: 118000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found by measurement while verifying TASK-117 AC5 at a 356px viewport, in a same-origin iframe
(window resizing does not change the page viewport on this display — see CLAUDE.md TW-004).

`DashboardPanel`'s wide variant is `'dashboard-panel-wide md:col-span-5 md:row-span-1'`
(`App.tsx:82`). The span is `md:` only, and `.dashboard-panel-wide` in `index.css:32-39` sets
typography and padding but **no `grid-column`**. Below 768px the grid is plain `grid-cols-2`, so
every "wide" panel is one of two columns — measured at **148px** each:

    Email decisions       148px      Total                148px
    New high priority     148px      Active applied       148px
    Active interviews     148px      Due follow-ups       148px
    Upcoming interviews   148px  <-- wide
    Application pace      148px  <-- wide
    Conversion funnel     148px  <-- wide
    Source effectiveness  148px  <-- wide

Two consequences, one cosmetic and one not:

**1. Source effectiveness overflows the viewport.** Its `<table class="w-full text-left text-xs">`
has an intrinsic width of **252px** inside a 148px column. In column 1 the spill is absorbed by the
gap; in column 2 it runs off the right edge and the whole document scrolls sideways — measured
`documentElement.scrollWidth` **443px against a 356px viewport**. Which column it lands in is pure
parity, so adding or hiding any panel before it flips the bug on and off. TASK-117 adding a panel at
the front is what surfaced it; the defect is older than that change.

**2. A "wide" panel is not wide on the device where width is scarcest.** Application pace, the
conversion funnel and source effectiveness are all data-dense layouts rendered into 148px.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 At a 360px viewport, `document.documentElement.scrollWidth` is not greater than the viewport width on the dashboard — measured in a same-origin iframe, with every panel visible, and re-measured after reordering panels so column parity changes
- [ ] #2 No panel's content is wider than the panel that contains it: for each panel, the widest descendant's `getBoundingClientRect().width` is <= the panel's own width, or that descendant sits in its own `overflow-x:auto` container so it scrolls itself instead of the page
- [ ] #3 Wide panels are full-width below 768px, or the reason they are not is written down in `index.css` beside the rule — the current state is neither, and reads as an oversight rather than a decision
- [ ] #4 The fix is not per-panel: it holds for any panel added later without that panel having to know about it. TASK-117 shipped a `data-panel="mailbox_review"` escape hatch for exactly this reason; that rule is deleted when this task lands
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
`.dashboard-panel-wide{grid-column:1 / -1}` inside a `@media (max-width:767px)` block is the
one-line candidate, but it changes the mobile appearance of four already-shipped panels, which is
why TASK-117 did not do it as a drive-by. Whoever takes this should look at all four at 360px first
and decide deliberately.

Note also that `index.css:41-66` targets `.mb-4.grid.grid-cols-2.gap-3.md\:grid-cols-7` while the
dashboard grid in `App.tsx` renders `md:grid-cols-5`. Those selectors match nothing today. Not this
task's job to fix, but worth confirming before adding more CSS that depends on the grid's class list.
<!-- SECTION:NOTES:END -->
