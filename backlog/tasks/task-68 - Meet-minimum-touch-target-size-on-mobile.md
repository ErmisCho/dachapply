---
id: TASK-68
title: Meet minimum touch target size on mobile
status: Done
assignee:
  - '@claude'
created_date: '2026-08-15 21:05'
labels:
  - frontend
  - mobile
  - accessibility
dependencies: []
priority: medium
ordinal: 73000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Interactive controls are well under the 44x44px touch target that WCAG 2.2 (2.5.8 Target Size, Minimum, which sets 24x24 as the AA floor) and both platform guidelines recommend. Computed from the utility classes in frontend/src/index.css, not measured in a browser:

- `.btn`, `.btn-primary`, `.btn-danger`, `.btn-muted` (index.css:26-28) are `px-3 py-1.5 text-xs`: 12px text with roughly a 16px line box, plus 6px padding each side and a 1px border, so about **30px** tall. These are the main action buttons across the whole app.
- `.nav-link` (index.css:71) is `px-1.5 py-0.5 text-[11px]`: about **20px** tall, the smallest target in the app.
- The bare `button` element rule (index.css:24) is `px-3 py-2` at inherited size, so roughly **40px** - the closest to acceptable, and only used where no `.btn-*` class is applied.

This matters for the actual job-search loop: triaging postings on a phone means repeatedly hitting status selects, notes and stage controls inside dense mobile job cards.

Surfaced 2026-08-15 during the TASK-9 verification pass. Not fixed there because it is a global change to shared classes with wide visual blast radius, well outside that task's acceptance criteria.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Interactive controls in the mobile job card and the public submit form present at least a 44px tap target
- [x] #2 Desktop density is preserved - the fix is scoped to touch or narrow viewports rather than enlarging every button everywhere
- [x] #3 The change is verified at 360px and 430px, the band index.css already special-cases
<!-- AC:END -->

## Outcome (2026-08-15)

Implemented in index.css inside the existing `@media (max-width: 1023px)` block rather than a new
`pointer: coarse` query, keeping every mobile override in one place: a `min-height:2.75rem` floor on
button, .btn, .btn-primary, .btn-danger, .btn-muted, input, select, textarea and summary, plus
`display:inline-flex` centring for bare buttons so the extra height does not push text off-centre,
and an explicit override for .mobile-badge-button which carried a pre-existing `min-height:0`.
A pre-existing 2.4rem rule on .mobile-job-fields buttons was raised to 2.75rem for consistency.

MEASURED in a real browser at true viewport widths, using a same-origin iframe because window
resizing did not change the page viewport on this display:

    width    media query   buttons      .btn-*       inputs/selects   controls under 44px
    360px    matches       44.0         44.0         44.0             0
    430px    matches       44.0         44.0         44.0             0
    1024px   no match      28.0-36.0    28.0-36.0    36.0             12
    1280px   no match      28.0-36.0    28.0-36.0    36.0             12

AC1 met: nothing below 44px at either phone width. AC3 met by measurement rather than assertion.
AC2 met: 1024px and 1280px are byte-identical to each other and unchanged from before the edit,
because the whole rule set sits behind a max-width boundary - desktop density is untouched.

.nav-link was deliberately NOT enlarged. It is visible from 640px up, so bumping it would have
broken TASK-67 AC3. The mobile destinations added under TASK-67 use .btn-muted instead, which the
floor above already covers - measured at 44px on mobile against 21.6px for the desktop nav row.
## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Enlarging `.btn-*` outright would wreck the deliberately dense desktop table, so AC2 exists to prevent that. Two approaches that preserve it:
- A `@media (hover: none) and (pointer: coarse)` block bumping min-height on `.btn-*` and `.nav-link`. Targets touch devices rather than narrow windows, so a small desktop window is unaffected.
- Or extend the existing `@media (max-width: 1023px)` block that already restyles `.mobile-job-fields`, keeping all mobile overrides in one place.

The visual bump can be absorbed with `min-height` plus centred content instead of extra padding, which avoids reflowing the card grid.

Worth doing together with TASK-67: revealing the nav links on mobile without fixing `.nav-link` sizing would add several 20px targets.
<!-- SECTION:NOTES:END -->
