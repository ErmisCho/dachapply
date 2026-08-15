---
id: TASK-68
title: Meet minimum touch target size on mobile
status: To Do
assignee: []
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
- [ ] #1 Interactive controls in the mobile job card and the public submit form present at least a 44px tap target
- [ ] #2 Desktop density is preserved - the fix is scoped to touch or narrow viewports rather than enlarging every button everywhere
- [ ] #3 The change is verified at 360px and 430px, the band index.css already special-cases
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Enlarging `.btn-*` outright would wreck the deliberately dense desktop table, so AC2 exists to prevent that. Two approaches that preserve it:
- A `@media (hover: none) and (pointer: coarse)` block bumping min-height on `.btn-*` and `.nav-link`. Targets touch devices rather than narrow windows, so a small desktop window is unaffected.
- Or extend the existing `@media (max-width: 1023px)` block that already restyles `.mobile-job-fields`, keeping all mobile overrides in one place.

The visual bump can be absorbed with `min-height` plus centred content instead of extra padding, which avoids reflowing the card grid.

Worth doing together with TASK-67: revealing the nav links on mobile without fixing `.nav-link` sizing would add several 20px targets.
<!-- SECTION:NOTES:END -->
