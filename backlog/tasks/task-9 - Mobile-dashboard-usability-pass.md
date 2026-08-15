---
id: TASK-9
title: Mobile dashboard usability pass
status: Done
assignee:
  - '@claude'
created_date: '2026-06-20 09:51'
updated_date: '2026-06-20 09:54'
labels:
  - P2
  - frontend
  - mobile
  - ux
  - phase-3
milestone: m-3
dependencies:
  - TASK-5
  - TASK-7
priority: low
ordinal: 9000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Make the core dashboard usable on phones for quick checks and friend submissions.
<!-- SECTION:DESCRIPTION:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
NO CODE WAS WRITTEN FOR THIS TASK. It was already implemented across ~13 earlier commits on this
branch (f7b71d0 "add mobile job card layout" through 4470399 "Align mobile feedback badge height")
and the ticket had simply never been closed. Verified rather than rebuilt.

AC1: Dashboard renders a card list in `space-y-3 p-3 lg:hidden` and hides the table behind
`hidden w-full table-fixed ... lg:table`, so any width below 1024px gets cards and never the table.
index.css raises font sizes for phones specifically, and a `@media (max-width:430px)` rule collapses
.mobile-job-fields from two columns to one, covering the 360-430px band.

AC2: the mobile card uses `min-w-0 flex-1` with `break-words` for text and a `shrink-0` action
cluster, so controls wrap instead of overflowing; the bulk-action and filter bars use flex-wrap and
a responsive grid. The one horizontally scrolling element is a decorative badge-chip row, not an
action, which is what the AC's "where possible" allows.

AC3: the public submit form is a fluid max-w-3xl layout, a global rule makes every input full-width,
and optional fields start collapsed in a details element in publicMode.

Verified by reading the shipped breakpoints and classes, not by screenshotting a live device -
stated plainly so the evidence is not overclaimed.

FOLLOW-UPS FOUND, deliberately not fixed here as both are outside these ACs:
- Nav hides Submit-for-friend / Data / Bookmarklet / Profile below `sm:` with no hamburger
  replacement. No AC is blocked because the dashboard has its own always-visible CTA, but it is a
  real mobile-nav gap. (TASK-8's feedback link was placed in the profile dropdown as well as the nav
  precisely because of this.)
- Global button height is ~36-38px, below the 44px touch-target guideline. Fixing it is a global,
  high-blast-radius change.
<!-- SECTION:NOTES:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Dashboard table/cards are readable on common mobile widths
- [x] #2 Important job actions are reachable without horizontal scrolling where possible
- [x] #3 Public submit page works comfortably on mobile
<!-- AC:END -->
