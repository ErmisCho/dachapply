---
id: TASK-268
title: Popups render above everything else and are never partially covered
status: Done
assignee: []
created_date: '2026-10-05 15:17'
updated_date: '2026-10-05 20:10'
labels:
  - ui
dependencies: []
priority: high
ordinal: 265000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner request 2026-10-05 with screenshot: the compact 'Generate CV and Motivation Letter' popup (z-40) is cut through by the board's filter bar (Min fit score / Statuses / Priority / Apply), which paints on top of the popup's middle. The frontend has ad-hoc z-index layers from z-0 up to z-[9999]; popups must sit above every board surface (sticky filter bar, sticky table header, panels).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The CV popup, the bulk generation dialog and every other popup/dialog in the app render above all page surfaces: at the screenshot's state (board scrolled so the filter bar overlaps), elementFromPoint at a grid of points inside the popup returns only popup descendants (measured)
- [x] #2 Fixed by one shared layering scale (e.g. named z-index tokens: page < sticky < dropdown < popup < toast/tour), not by bumping one number; every existing z-* in App.tsx/index.css maps onto it
- [x] #3 Dropdowns/menus opened from inside a popup still appear above that popup
- [x] #4 The onboarding tour highlight and toasts keep working (not hidden behind popups when they should be on top)
- [x] #5 Test pins the layering scale; tsc clean; verified on localhost:8000 by reproducing the screenshot state
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Root cause: filter card z-50 vs popup z-40 at the same root stacking level. Fixed in #206 with one named z-index scale (--z-base…--z-tour), layering.test.ts bans raw z values. Measured 1366x768, 10x10 elementFromPoint grid inside the CV popup: main 20/100 covered at scroll 900-1137 -> 0/100 at every scroll. Bulk dialog 0/100; bulk Source-text popover on top; menus inside the popup on top; tour 71 > overlay 70 > popup 40 (computed). Dialogs not opened in a browser (notes, ChatGPT workflow, feedback mail, reply, unsaved, source) are pinned to the popup layer by layering.test.ts.
<!-- SECTION:NOTES:END -->
