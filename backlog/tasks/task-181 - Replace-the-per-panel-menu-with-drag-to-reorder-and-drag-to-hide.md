---
id: TASK-181
title: Replace the per-panel menu with drag to reorder and drag to hide
status: Done
assignee: []
labels:
  - frontend
  - ux
  - accessibility
dependencies:
  - TASK-102
  - TASK-174
priority: high
ordinal: 181000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner, 2026-08-24, with a screenshot of the board: *"I want this button from the panels to be removed,
and instead user being able to drag and drop and rearrange the panels and also with drag and drop
being able to hide a panel. But once a panel is hidden, where can they be reenabled?"*

The button is the `⋮` **Panel options** control that `DashboardPanel` renders in the top-right corner
of every panel. It carries three actions: Move left, Move right, Hide.

**Answer to the owner's question, established by reading the code and confirmed live in wave 2:** the
existing **Panels** button in the board's top-right corner already lists every panel id with a
Show/Hide toggle and a Reset panels action. A hidden panel is re-enabled there, and that is where
`mailbox_unmatched` was switched back on during TASK-174's verification. No new surface is needed for
re-enabling; the owner simply had not seen that menu do it.

**The trap this task exists to avoid.** `DashboardPanel` already carries a hover-only cluster of the
same three buttons (`hidden group-hover:flex`), and TASK-102's comment on it is explicit:

> `hidden group-hover:flex` removed these from the tab order entirely (display:none), so
> `group-focus-within` could never fire from inside them either — unreachable by touch or keyboard.
> The hover cluster stays as a pointer-only shortcut (AC3); the always-visible menu button below is
> the one real trigger/tab-stop/tap-target all three actions now route through.

So the `⋮` is currently the ONLY keyboard- and touch-reachable path to Move left / Move right. Hide
survives its removal because the Panels menu offers it; **reordering does not**. HTML5 drag-and-drop
does not fire on touch at all, so "drag to rearrange" is a pointer-only capability by construction —
deleting the `⋮` without replacing the reorder path would leave the board permanently unorderable on
a phone and by keyboard, which is TASK-102's defect returning by a different route.

The resolution is to move Move-left/Move-right into the Panels menu alongside each panel's existing
Show/Hide, so all three actions keep a non-pointer path while every panel loses its corner button.

**Drop target for hiding — owner decision, 2026-08-24:** a labelled drop zone that appears only while
a drag is in progress. Chosen over dropping onto the Panels button, dropping outside the grid (too
easy to trigger by a sloppy drag, and there is no undo), and menu-only.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The per-panel `⋮` button is gone from every panel, and so is the hover-only button cluster it replaced — neither renders in the DOM, verified by counting them before and after
- [ ] #2 Panels can be reordered by dragging one onto another, and the new order persists across a reload
- [ ] #3 A drop zone appears ONLY while a panel drag is in progress, is labelled in words, and dropping a panel on it hides that panel
- [ ] #4 Move left, Move right and Hide all remain reachable without a pointer — state where each one now lives and prove each is a keyboard tab stop that performs the action
- [ ] #5 A hidden panel is re-enabled from the Panels menu, and the answer to "where do they come back?" is discoverable from the UI itself rather than only from this task file
- [ ] #6 TASK-174's default-hidden seeding still holds: a brand-new profile still gets `mailbox_unmatched` hidden exactly once, and an explicit Show still survives a reload
- [ ] #7 TASK-134 still holds: a drag starting on message text inside a panel still selects text instead of dragging the panel, measured after this change
- [ ] #8 Verified at desktop width and at a narrow width; if a true narrow viewport is unreachable in this environment, say so and state what was measured instead
- [ ] #9 Frontend typecheck and tests green; `localhost:8000` loads the board without an application error after a rebuild in the owner's checkout
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
`DashboardPanel` (App.tsx) already sets `draggable` on the whole panel and wires
`onDragStart`/`onDrop`/`onDragOver` to `Dashboard`'s `dropPanel`/`savePanelOrder`, so reordering by
drag largely exists — check what is already working before building it again. TASK-134's
`allowDrag` mousedown guard on `.mailbox-selectable` must survive untouched (AC7).

Do NOT delete `hidePanel`/`revealPanel`/`movePanel`. They are the actions; only their trigger changes.

The drop zone must not shift the grid layout when it appears, or panels will jump under the cursor
mid-drag and the drop will land on the wrong target. Reserve the space or overlay it.

`dragend` must clear the drop zone even when the drag is cancelled with Escape or dropped nowhere —
a drop zone stuck on screen after a cancelled drag reads as a broken page.
<!-- SECTION:NOTES:END -->
