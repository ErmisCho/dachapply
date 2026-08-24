---
id: TASK-173
title: Portal the row feedback popup out of the table wrapper
status: Done
assignee: []
labels:
  - frontend
  - refactor
dependencies: []
priority: low
ordinal: 173000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Split out of TASK-167 on 2026-08-23. It is the prerequisite that blocks it, and it is worth doing on
its own terms.

The row-level feedback editor renders as a plain absolutely-positioned child of the table row:

    {feedbackEditor===j.id && <div onClick={e=>e.stopPropagation()}
        className="absolute left-0 top-full mt-2 z-[9999] max-h-[calc(100vh-7rem)] w-[22rem]
                   max-w-[calc(100vw-2rem)] cursor-default overflow-auto break-words rounded-xl ...">

Two things about it are in tension. It is sized against the **viewport** (`max-h-[calc(100vh-7rem)]`,
`max-w-[calc(100vw-2rem)]`) and given `z-[9999]`, so it is written as though it floats above the
page — but it is positioned and clipped by its ancestors, which are the board's table wrappers. It
appears 4 times in `App.tsx` (desktop row and mobile card).

That mismatch is why `.premium-card` had to be split into an outer `overflow-y-visible` and an inner
`overflow-x-auto` in TASK-139: the outer one exists purely so this popup is not clipped vertically.
Every future change to the table's scroll containers has to work around it — TASK-167 is already
blocked by exactly this, because giving the wrapper the bounded height that `position: sticky`
requires would clip the popup.

**This is cheaper than it looks.** `createPortal` is already imported and used **5 times** in the same
file, so the mechanism, the import and the local conventions all exist. The work is the positioning,
not the plumbing.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The feedback popup renders through `createPortal` to `document.body` rather than as a descendant of the table wrappers, using the same portal idiom already present in `App.tsx`
- [ ] #2 It appears in the same visual position relative to its row as it does today, verified by measuring its bounding box against the row's before and after — not by screenshot impression
- [ ] #3 It tracks its row on scroll and on resize, verified by measuring its position after a scroll rather than only on open
- [ ] #4 Existing behaviour is preserved: outside-click dismissal, the `stopPropagation` that keeps a click inside it from reaching the row, keyboard dismissal if present today, and its own internal scrolling when content is tall
- [ ] #5 Both occurrences are converted — the desktop table row and the mobile card — or the notes state why one is deliberately left
- [ ] #6 With the popup portalled, the outer `overflow-y-visible` wrapper is shown to be no longer required for THIS reason, and either removed or explicitly kept with the remaining reason stated; TASK-139's horizontal scrolling must still work, measured
- [ ] #7 Verified at desktop width and at a width where the mobile card layout renders
- [ ] #8 Frontend typecheck and tests green; `localhost:8000` loads the board without an application error after a rebuild in the owner's checkout
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Do not remove the outer wrapper speculatively. AC6 asks for it to be shown unnecessary first — TASK-139
was caused by exactly that kind of confident simplification of these wrappers, and its own comment in
`index.css` records the result.

Unblocks TASK-167 (the sticky table header), which becomes a small CSS change once this lands.
<!-- SECTION:NOTES:END -->
