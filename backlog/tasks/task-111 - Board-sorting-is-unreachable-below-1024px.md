---
id: TASK-111
title: Board sorting is unreachable below 1024px
status: To Do
assignee: []
labels:
  - frontend
  - accessibility
  - ux
dependencies: []
priority: medium
ordinal: 112000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
TASK-108 made the board sortable by status and by up to three columns at once, via clickable column
headers. Those headers live on the board `<table>`, which is `hidden … lg:table` — so **none of it
exists below 1024px**. Below that breakpoint the board renders as cards and the only sorting control
is the original four-option preset `<select>`.

Measured 2026-08-16 with the same session and dataset at three widths:

     390px  sortable headers in DOM=6  RENDERED=0  preset <select> visible=true
     768px  sortable headers in DOM=6  RENDERED=0  preset <select> visible=true
    1024px  sortable headers in DOM=6  RENDERED=6  preset <select> visible=true

A phone user therefore gets: `Sort: recommended`, `Sort: fit score`, `Sort: newest`,
`Sort: feedback due` — and **no way to sort by status at all**, which was the headline request, and no
way to combine two keys.

Note the headers are present in the DOM but `display:none`, which also removes them from the tab
order. So this is not "a small-screen layout that omits a feature"; it is the same class of defect as
TASK-102 (controls that exist but cannot be reached), just triggered by viewport instead of hover.

Found by the coordinator during TASK-108 verification. TASK-108's AC6 is satisfied where the controls
render — they are keyboard-operable, tap-operable and 44px at >=1024px — so this is filed rather than
folded in, per TW-005: the gap gets its own paper trail instead of quietly widening or relaxing that
task's criteria.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A user on a 390px viewport can sort the board by status
- [ ] #2 A user on a 390px viewport can apply at least two sort keys with an explicit precedence, or the decision to allow only one key on small screens is recorded with its reasoning
- [ ] #3 Whatever control is added is operable by touch and by keyboard, with 44px targets, and is not hidden behind hover or a modifier key
- [ ] #4 The current sort is visible on small screens, not just implied
- [ ] #5 Verified at 390px in a real browser, with the applied ordering read back from the request the UI actually sends
- [ ] #6 No new axe violations at 390px, and `npx tsc --noEmit` / `npm test` stay clean
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Cheapest option that covers AC1 and probably AC2: extend the existing preset `<select>` — which is
already visible at every width — into a small sort sheet, or simply add the status options to it
(`Sort: status`, `Sort: status then fit`). That reuses a control that is already rendered, already
accessible and already wired to `f.ordering`; the wire contract from TASK-108 takes a comma-separated
string, so a preset can encode two keys with no backend change at all.

Only reach for a bespoke mobile sort UI if a preset list genuinely cannot express what is needed. The
backend already supports everything here — this is purely about giving small screens a control.

Worth checking while in here: whether the board table should become horizontally scrollable at
tablet widths instead of being replaced by cards, which would make the real headers available from
768px up and shrink this task considerably.
<!-- SECTION:NOTES:END -->
