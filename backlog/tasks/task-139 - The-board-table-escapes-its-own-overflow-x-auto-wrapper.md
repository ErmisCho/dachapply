---
id: TASK-139
title: The board table escapes its own overflow-x-auto wrapper
status: Done
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
- [x] #1 `document.body.scrollWidth <= document.documentElement.clientWidth` on the board page at 1278px with the table populated — measured in a browser, since this whole task exists because a computed value did not match the markup's intent
- [x] #2 The table itself remains horizontally scrollable inside its wrapper: it has more columns than fit and hiding them is not the fix. Verified by asserting the wrapper's `scrollWidth > clientWidth` while the page's does not
- [x] #3 Why the computed `overflow-x` resolved to `visible` is established and written down, not worked around by guessing — `overflow-y-visible` next to `overflow-x-auto` is the suspect and the resolution rule for that pair is specified behaviour, so this is knowable
- [x] #4 Whatever governs `overflow-y` today is preserved: the wrapper carries `overflow-y-visible` on purpose (row hover popups and dropdowns escape the card vertically), and clipping them would trade a horizontal bug for a worse vertical one — verified by opening a row popup after the change
- [x] #5 Checked at 360px and 430px too, where the table is `hidden` and the card layout renders instead, so the fix must not introduce an overflow in the layout that currently has none
- [x] #6 `npx tsc --noEmit` and `npm test` clean
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-08-19, measured in Chrome against the built bundle at localhost:8000 (same-origin iframe at the
target widths): AC1 body.scrollWidth 1260 <= clientWidth 1260 at a 1278px frame (was 1637 vs 1278);
AC2 wrapper clientWidth 1226, scrollWidth 1621, scrollLeft=200 sticks; AC5 342<=342 at 360 and
412<=412 at 430. AC3's real mechanism was NOT the CSS pairing rule: index.css carried
`.premium-card.relative.z-0.overflow-x-auto.overflow-y-visible{overflow:visible!important}` inside
the 1024px media query, beating the Tailwind utility on both axes — removed, and the wrapper split
into an outer always-visible div plus an inner overflow-x-auto div (documented at both sites).
AC4: feedback popup opened on the last interview row (77 of 88) rendered fully, 259px tall, nothing
clipped (wrapper grows to content height, 6080==6080; the Match/gap popup is portalled to body).

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
