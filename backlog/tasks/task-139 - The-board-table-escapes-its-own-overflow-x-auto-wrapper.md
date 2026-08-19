---
id: TASK-139
title: The board table escapes its own overflow-x-auto wrapper
status: To Do
assignee: []
labels:
  - frontend
  - ux
priority: medium
ordinal: 139000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found while measuring TASK-138, and deliberately NOT fixed there — it is a different component with a
different cause, and folding it into a mailbox fix would have hidden it.

TASK-138 AC1 asked for `document.body.scrollWidth <= window.innerWidth`. After TASK-138's fix the
mailbox panel contributes nothing (`scrollWidth === clientWidth === 1246`), and yet the page still
scrolls sideways:

    viewport (clientWidth)   1278
    document.body.scrollWidth 1637      -> overflows by 359px

Isolated by hiding elements and re-measuring: the overflow survives hiding the mailbox panel, so the
mailbox is not the source. Walking up from the element whose right edge is exactly 1637:

    TABLE  .job-table.hidden.w-full.table-fixed        w 1621  right 1637  scrollWidth 1621
    DIV    .premium-card.relative.z-0.overflow-x-auto.overflow-y-visible
                                                       w 1246  clientWidth 1244  scrollWidth 1621
                                                       computed overflow-x: VISIBLE
    MAIN   .w-full.px-4.py-5                           clientWidth 1278  scrollWidth 1637
    BODY                                               clientWidth 1278  scrollWidth 1637

The wrapper is asking to scroll its own table (`overflow-x-auto`) and is not doing it — its computed
`overflow-x` reads `visible`, so the 1621px table escapes into `MAIN` and out to `<body>`. The
element pairs `overflow-x-auto` with `overflow-y-visible`, which is the combination CSS defines
special behaviour for, and it is not resolving the way the markup intends.

This is pre-existing. It is not a regression from TASK-134/136/137/138 — the mailbox blowout was
simply larger (2277px), so this one was hidden underneath it.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 `document.body.scrollWidth <= document.documentElement.clientWidth` on the board page at 1278px with the table populated — measured in a browser, since this whole task exists because a computed value did not match the markup's intent
- [ ] #2 The table itself remains horizontally scrollable inside its wrapper: it has more columns than fit and hiding them is not the fix. Verified by asserting the wrapper's `scrollWidth > clientWidth` while the page's does not
- [ ] #3 Why the computed `overflow-x` resolved to `visible` is established and written down, not worked around by guessing — `overflow-y-visible` next to `overflow-x-auto` is the suspect and the resolution rule for that pair is specified behaviour, so this is knowable
- [ ] #4 Whatever governs `overflow-y` today is preserved: the wrapper carries `overflow-y-visible` on purpose (row hover popups and dropdowns escape the card vertically), and clipping them would trade a horizontal bug for a worse vertical one — verified by opening a row popup after the change
- [ ] #5 Checked at 360px and 430px too, where the table is `hidden` and the card layout renders instead, so the fix must not introduce an overflow in the layout that currently has none
- [ ] #6 `npx tsc --noEmit` and `npm test` clean
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
AC4 is the trap and the reason this is not a one-word change. `overflow-y-visible` is on that wrapper
deliberately — the board's row popups are positioned children that must escape the card. Any fix that
makes the wrapper a real scroll container in both axes will clip them, which is how this pairing got
written in the first place. A wrapper that scrolls horizontally and does not clip vertically is the
requirement; if CSS cannot give both on one element, the honest answer is two elements, and AC3 exists
so that conclusion is reached by reading the spec rather than by trying classes until one looks right.

Do not "fix" this by putting `overflow-hidden` on `MAIN` or `<body>`. That hides the symptom at the
page level, leaves the table clipped with no way to reach its right-hand columns, and would make
AC2 fail while AC1 passes.
<!-- SECTION:NOTES:END -->
