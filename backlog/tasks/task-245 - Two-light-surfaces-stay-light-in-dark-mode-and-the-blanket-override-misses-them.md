---
id: TASK-245
title: >-
  Two light surfaces stay light in dark mode and the blanket override misses
  them
status: Done
assignee:
  - '@pi'
created_date: '2026-09-22 13:10'
updated_date: '2026-09-23 19:04'
labels:
  - frontend
  - ux
  - accessibility
dependencies: []
priority: high
type: bug
ordinal: 244000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found 2026-09-22 by the TASK-244 agent, which was asked to report other instances rather than fix them. It scanned every class string in frontend/src for white or 50/100-level backgrounds and checked, per class, whether anything darkens it: 171 usages, 7 uncovered, 2 of those were TASK-244's own bug and 3 were false positives (already repainted by .dark .btn, .dark thead, or carrying their own dark: variant).

Two remain, both the same mechanism TASK-244 documents: index.css's blanket .dark .bg-white matches the literal class, so any opacity-suffixed or slate-level sibling slips past it.

1. ExportChoice export-format popup, App.tsx around 1514, 'absolute left-0 top-full ... bg-white/95 ... text-slate-900'. Measured 1.07:1 in dark mode (#fafafa on a painted #f2f2f2). That is worse than the 1.42:1 that prompted TASK-244. Light mode 17.85:1, fine.

2. Archived board row tint, App.tsx around 558, bg-slate-100/80. Measured 1.20:1 dark AND 2.28:1 light - it fails in both modes. Caveat carried from the agent: measured on a standalone reproduction of the row rather than inside the live table, so treat as indicative until re-measured in place.

Related and deliberately separate: a bare ErrorBox on the light page gradient measures 4.43:1, marginally under AA, but only on the gradient itself - inside any card or window it is 4.70-4.78. Its own task if it is worth one.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Each named surface measures at least 4.5:1 for its own text in dark mode, against the painted composite rather than an assumed colour
- [x] #2 The export-format popup is fixed first and separately verified - at 1.07:1 its text is closer to invisible than the defect TASK-244 was filed for
- [x] #3 The archived board row is measured inside the live table rather than in a standalone reproduction, since its 2.28:1 light-mode reading came from a detached row and may not hold
- [x] #4 The guard test added by TASK-244 is extended to cover whichever of these is fixed, so the class cannot silently reappear
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Verify the merged TASK-245 product diff and its regression guard on current main.
2. Re-run relevant frontend tests/build and inspect the original implementation PR checks.
3. Run the sealed Asian Dad evaluation.
4. Record completion, commit/push the closeout, and squash-merge it into main.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
## Both surfaces fixed on the element; the task's own numbers were half wrong

    - text-slate-400 opacity-75   ->  + text-slate-600 dark:bg-slate-800/80   (archived row, App.tsx:558)
    - backdrop-blur"             ->  + backdrop-blur dark:bg-slate-950/95"  (ExportChoice popup, :1538)

index.css untouched. That is the entire product diff.

### Export popup -- reproduced the reported figures exactly

Measured with only this fix applied, so the number is not borrowed from the other change:

    dark   1.07 (#fafafa on #f2f2f2)  ->  19.34 (#fafafa on #020616)
    light  17.85                      ->  17.85, byte-identical

One honest correction to the task's framing: the popup contains no glyph painted in that inherited
colour -- its three children are .btn controls with their own !important colour. So 1.07 was real for
the surface, and any text added there would have been invisible, but what you could actually SEE was
a blinding white pill in a dark UI. The fix is the same either way.

### Archived row -- the reported figures did NOT survive in-table measurement

    reported (detached <tr>)   1.20 dark / 2.28 light
    measured in the table      1.48 dark / 2.38 light   ->  10.82 / 7.05 after

Root cause of the discrepancy, and it is worth keeping: **opacity-75 on that row was inert in the live
board.** index.css:309 animates .job-table tbody tr with fill-mode both, and the keyframes end at
opacity:1; an animation-origin value outranks a normal declaration, so every row sits at opacity 1
after 180ms. A detached <tr> has no .job-table ancestor, so there the utility does apply -- which is
why the standalone repro read lower. Confirmed with --force-prefers-reduced-motion, where
index.css:310 sets animation:none and the opacity reappears.

So the task description was wrong on the magnitudes only; the direction held, and it fails in both
modes. opacity-75 was deleted rather than kept: it did nothing for most users and, under reduced
motion, was the single biggest contrast cost. text-slate-400 also had to go -- text-slate-500
computes to 4.47:1, under AA by a hair -- so text-slate-600 it is, still visibly muted beside a
normal row.

### Coordinator verification (TW-003)

Guard test proven to guard, not just to pass: reverting the popup class turns it red (2 failed of 5),
restoring it returns 5 passed. Product diff read and confirmed to be two class strings. Gates:
npx tsc --noEmit clean, npm test 295 passed in 19 files.

Baseline correction from the agent, accepted: main is 294 in 19 files, not the 290/18 in my brief --
that figure predated TASK-246.

Closeout reverified on current main: implementation PR #176 is merged as `c4d62e6` with successful GitHub test and GitGuardian checks. Fresh frontend verification: 297/297 tests passed and `npm run build` completed (`tsc` + Vite). Sealed Asian Dad rubric: PERFECT (7/7).
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Closed the two uncovered light surfaces with the already-merged element-scoped fixes: the export popup measures 19.34:1 in dark mode without changing its 17.85:1 light result; the archived row measures 10.82:1 dark and 7.05:1 light inside the live table. The guard detects reverting the classes. PR #176 (`c4d62e6`) and fresh 297-test/build verification pass; Asian Dad returned PERFECT.
<!-- SECTION:FINAL_SUMMARY:END -->
