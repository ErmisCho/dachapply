---
id: TASK-183
title: Show where a dragged panel will land, and rearrange live
status: Done
assignee: []
labels:
  - frontend
  - ux
dependencies:
  - TASK-181
priority: high
ordinal: 183000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner, 2026-08-24, immediately after TASK-181 shipped drag-to-reorder: *"make also the drag and drop
user intuitive like where the panel is going to be positioned after letting go of the panel and that
as soon as I drag a panel, that I can rearrange it."*

TASK-181 made the gesture work but gave it no feedback. Today the panels sit perfectly still for the
whole drag and the board only rearranges on release, so the owner is aiming blind: there is nothing on
screen that says which slot the panel is heading for, and no way to tell a drop that will move it from
a drop that will do nothing. TASK-181's own bug — a forward drag onto the next panel being a silent
no-op — survived review precisely because the UI gave no signal either way.

Two things are being asked for, and they are distinct:

1. **Show the destination.** While dragging, the board must show where the panel will land if released
   now.
2. **Rearrange during the drag, not on release.** The reordering should follow the cursor as it moves
   over other panels, so the owner is arranging the board rather than aiming at it and hoping.

Both are the same underlying change: the order shown during a drag becomes a live preview of the
result, committed on drop and abandoned if the drag is cancelled.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 While a panel is being dragged over another, the board shows the resulting arrangement — state what the feedback is (panels shifting into their new positions, a gap where it will land, an insertion marker, or a combination) and where it appears
- [ ] #2 The preview updates as the cursor moves to a different target, and it matches exactly what a release would produce — measured by comparing the previewed order against the committed order for at least one forward and one backward drag
- [ ] #3 Releasing commits the previewed arrangement, and the committed order persists across a reload
- [ ] #4 Cancelling the drag (Escape, or releasing over nothing) restores the original order exactly — nothing is left half-moved, measured before and after
- [ ] #5 A drag that would change nothing is visibly distinguishable from one that would: dropping a panel back on itself, or on a target that leaves the order unchanged, does not falsely signal a move
- [ ] #6 The dragged panel itself remains identifiable during the drag — the owner can see which panel they are holding
- [ ] #7 TASK-181's hide drop zone still appears only during a drag, still hides on drop, and still clears on dragend; the live preview must not leave the grid shifted when the panel is dropped on the hide zone instead
- [ ] #8 TASK-181's keyboard path is untouched: Move left / Move right in the Panels menu still reorder, still tab-reachable
- [ ] #9 TASK-134 still holds: a drag starting on message text inside a panel selects text instead of dragging the panel, measured after this change
- [ ] #10 Frontend typecheck and tests green; `localhost:8000` loads the board without an application error after a rebuild in the owner's checkout
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
`reorderPanels(order, dragged, target)` already computes the resulting order and is unit-tested,
including the direction rule that TASK-181 got wrong (forward drags insert AFTER the target, backward
before). The live preview is that same function applied on `dragover` instead of only on `drop` — do
not write a second ordering rule, or the preview and the commit will disagree, which is a worse bug
than no preview at all.

The obvious shape is a preview order held in component state during the drag, rendered instead of the
saved order, committed by `savePanelOrder` on drop and dropped on `dragend`. `dragend` already exists
for the hide zone (TASK-181) and fires for every drag ending — successful, cancelled, or released over
nothing — so it is the natural place to abandon the preview.

Beware `dragover` firing continuously at high frequency on the same element: recompute only when the
target actually changes, or every mouse movement re-renders the whole grid.

No drag-and-drop library. HTML5 DnD is already wired here; this is a state change, not a new
mechanism.

Measurement note carried from TASK-180/181: this display floors the browser viewport near 1017 CSS px
and the app sends `X-Frame-Options: DENY`, so neither window resizing nor the same-origin iframe
technique reaches a narrow viewport. Drive drags with synthetic `DragEvent`s carrying a `DataTransfer`
and allow a tick between `dragstart` and `dragover` — React state must flush before the handler reads
it, which is a real measurement trap that cost a cycle on TASK-181.
<!-- SECTION:NOTES:END -->
