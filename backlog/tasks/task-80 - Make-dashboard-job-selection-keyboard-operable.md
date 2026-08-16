---
id: TASK-80
title: Make dashboard job selection keyboard-operable
status: Done
assignee:
  - '@claude'
created_date: '2026-08-16 00:43'
updated_date: '2026-08-16 13:10'
labels:
  - frontend
  - a11y
dependencies: []
priority: medium
ordinal: 85000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Row selection is the gate to Analyze, bulk status changes, CV generation, and export — and it works only via `<tr onClick>` / `<article onClick>` with no tabIndex, role, checkbox, or key handler (frontend/src/App.tsx:98). The only onKeyDown in the entire app is the Export dropzone (App.tsx:208).

A keyboard-only user cannot select a job at all, which means they cannot reach most of what the app does.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Each board row's selection can be toggled by keyboard (Space or Enter on a focusable control), on both the table and the mobile card layout
- [x] #2 Selection state is programmatically exposed (a real checkbox or aria-selected)
- [x] #3 Verified by an actual keyboard-only walkthrough: select two jobs and trigger Analyze without touching the pointer, recorded in the closing notes
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
A real checkbox per row is the lazy accessible answer — free focus, free semantics, free hit target (44px rule from TASK-68 applies on mobile). Keep the row-click behaviour; the checkbox is an addition, not a replacement.

### Closing notes (2026-08-16)

A real `<input type="checkbox">` per row in both the table and the mobile card, with
`aria-label={'Select ' + company + ' ' + title}` so a screen reader announces which row it is
selecting rather than fourteen identical "Select" controls. `aria-selected` was deliberately not
used: it is not valid on `role=row` inside a plain `<table>` and would have traded one axe violation
for another. Row-click selection is unchanged — the checkbox cell and the mobile `<label>` call
`stopPropagation`, so a click toggles exactly once — and shift-range select still works from the
checkbox via `e.nativeEvent.shiftKey`.

**AC3, the keyboard-only walkthrough, driven for real** (Playwright, pointer never used):

    focused control      INPUT[checkbox] "Select Z-Overdue probe"
    focus outline        solid 2px rgb(37, 99, 235)      <- had to be re-added; the shared
                                                            input rule applies outline-none
    Space                checked=true, bulk action bar appeared
    Space again          checked=false
    Enter on row 2       checked=true
    two rows selected    2
    Shift+Tab x5         focus reached "Analyze selected jobs"

So: two jobs selected and Analyze reached without touching the pointer. Note for a future task —
the bulk bar is rendered *before* the table, so reaching it from a row is a backwards traversal.
Operable, but not the natural forward flow.

**Mobile tap target, measured at 390px** rather than assumed:

    label.row-select-target   44 x 44 px      <- the hit area; clicking it activates the control
    input.row-select        21.6 x 21.6 px    <- the painted box

TASK-68's rule is about the tap target, and 44×44 is what a thumb actually gets, so this satisfies
it. Recording both numbers because the box itself is smaller and that is the kind of thing a later
reader would otherwise have to re-measure. The naive alternative — letting the global
`input { width: 100% }` rule apply — would have produced a 44px-tall checkbox stretched across the
whole card.

**Regression check on the riskiest part of the diff.** Adding a column shifted every `nth-child`
index in `index.css`, which silently breaks column hiding if any index is off by one. All eleven
column toggles were exercised one at a time and re-checked:

    columns: SELECT | PRIO | FIT | POSITION | LOC | STATUS | APPLICATION DATE |
             LAST UPDATE | FEEDBACK | MATCH / GAP | SKILLS | ADDED BY
    result: every toggle hid exactly its own column; the checkbox column never disappeared
<!-- SECTION:NOTES:END -->
