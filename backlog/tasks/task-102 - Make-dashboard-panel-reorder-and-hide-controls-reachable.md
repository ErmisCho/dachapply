---
id: TASK-102
title: Make dashboard panel reorder and hide controls reachable
status: Done
updated_date: '2026-08-16 19:40'
assignee:
  - '@claude'
created_date: '2026-08-16 14:30'
labels:
  - frontend
  - accessibility
dependencies: []
priority: medium
ordinal: 103000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`DashboardPanel`'s move-left / move-right / hide controls are `hidden group-hover:flex`. Because
`display:none` removes them from the tab order entirely, `group-focus-within` can never fire from
inside them either — so they are unreachable by touch **and** by keyboard, with no alternative path.

Found while implementing TASK-81, which fixed exactly this class of bug for the three disclosures
its AC3 names (the analyze per-job picker, the batch source-text preview, and the match-gap popup).
These panel controls are the same defect and were deliberately left alone rather than quietly
widened into that task's scope: fixing them needs a new affordance, not a `useDismiss` call, because
there is no trigger to attach to — the controls *are* the hover-revealed thing.

There is a partial workaround today: the "Panels" menu (which TASK-81 did make keyboard-operable)
can hide and show panels. Reordering has no non-pointer path at all.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Panel reorder and hide are operable by keyboard alone, verified by an actual keyboard-only walkthrough recorded in the closing notes
- [x] #2 The same controls are operable by tap on a touch device, with a target of at least 44px
- [x] #3 Desktop hover behaviour and panel density are not degraded for pointer users
- [x] #4 No new axe violations on the dashboard
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
A per-panel menu button (always visible, `aria-expanded`, wired to the existing `useDismiss` hook
from TASK-81) containing Move left / Move right / Hide is the smallest thing that satisfies all four
criteria — it gives a real trigger, a real tab stop and a real tap target, and reuses machinery that
already exists rather than adding a second dismissal mechanism.

Keeping the hover controls as a pointer-only shortcut alongside it is fine and covers AC3; they just
must not be the only path.

IMPLEMENTED as proposed, no deviation. `DashboardPanel` (frontend/src/App.tsx) now renders two
control clusters instead of one:
1. The original `hidden group-hover:flex` cluster (Move left / Move right / Hide) is unchanged except
   shifted from `right-2` to `right-11` to make room for #2 - same classes, same order, same
   pointer-only reveal, so desktop hover behaviour and panel density are unaffected (AC3).
2. A new always-visible "⋮" button per panel (`min-h-[2.75rem] min-w-[2.75rem]`, `aria-expanded`,
   `aria-label="Panel options for {panel label}"`, using `dashboardPanelLabels[id]` which already
   existed for the "Panels" show/hide menu) opens a dropdown with three real `<button>`s - Move left,
   Move right, Hide - each also `min-h-[2.75rem] min-w-[2.75rem]`. The trigger + panel are both inside
   the one ref passed to `useDismiss(menu, close)` (kind defaults to `'menu'`), matching the pattern
   the comment above `useDismiss` requires and the 9 other call sites already in this file - Escape
   closes it and focus returns to the trigger, an outside click closes it, and because these are real
   buttons (not `display:none` until hover) they are in the tab order and keyboard-activatable by
   construction, unlike the controls they wrap.

No new dependency, no new dismissal mechanism, no new component file - the whole diff is inside the
existing `DashboardPanel` function.

### Coordinator browser verification (2026-08-16) — all four ACs measured

Isolated stack (scratch sqlite, backend on :8010), authenticated as a seeded user with 9 dashboard
panels.

**AC1 — keyboard only, no pointer used at any point.** Panel order read from the panels' own
`aria-label`s before and after:

    before: ["Total","New high priority","Active applied","Active interviews","Due follow-ups", ...]
    focus lands on              button[Panel options for Total]
    aria-expanded before Enter  false
    Enter                    -> aria-expanded true
    Tab, Tab                 -> button[Move right]
    Enter                    -> order: ["New high priority","Total","Active applied", ...]
    Escape                   -> aria-expanded false, focus returned to the trigger button

The panel actually moved. That is the difference between "a menu opens" and "reorder is operable".

**AC2 — measured with `getBoundingClientRect()`, at desktop and phone width:**

                        1400px          390px (touch emulation)
    menu button      44.0 x 44.0      44.0 x 44.0
    "Move left"     150.0 x 44.0     150.0 x 44.0
    "Move right"    150.0 x 44.0     150.0 x 44.0
    "Hide"          150.0 x 44.0     150.0 x 44.0

At 390px the menu was opened by a real `tap()`, not a click, and `aria-expanded` went true.

**A false failure that nearly got recorded, and how it resolved.** The first pass reported
`"Hide" -> 34.6 x 44.0  *** UNDER 44 ***`. Scoping the query to the open dropdown instead of the whole
page showed *two* buttons answer to /hide/i: the new menu item at 150x44, and the legacy hover-cluster
button at 34.6x44. The failing measurement was of the pointer-only shortcut AC3 explicitly allows to
remain — not of the accessible path. Recorded because the sub-44px control does still exist on the
panel; it is simply no longer the only way in, which is exactly what this task asked for.

**AC3 — hover behaviour and density.** Measured with **no interaction at all** before reading, because
the first attempt tapped first and then reported `display:flex` at 390px, which was its own tap
inducing `:hover`:

    1400px   hover-cluster display=none   menu-button display=flex
     390px   hover-cluster display=none   menu-button display=flex

so the cluster is still hover-only and the new control is always present. Density cannot change
either: the new control is `absolute right-2 top-2 z-20` and the cluster moved to `absolute right-11`,
both out of layout flow. Grid measured 5 x 264px at 1400px and 2 x 173px at 390px.

**AC4 — axe (wcag2a/2aa/21a/21aa) on the dashboard:**

    menu closed: 0 violations
    menu open:   0 violations

Scanned with the menu open as well, since a dropdown that only exists while open is invisible to a
scan of the closed page — which is how a new violation would have been missed. No baseline diff was
needed: the after-count is 0, so "no new violations" holds regardless of the before-count.

<!-- SECTION:NOTES:END -->
