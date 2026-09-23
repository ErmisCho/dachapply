---
id: TASK-245
title: >-
  Two light surfaces stay light in dark mode and the blanket override misses
  them
status: To Do
assignee: []
created_date: '2026-09-22 13:10'
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
- [ ] #1 Each named surface measures at least 4.5:1 for its own text in dark mode, against the painted composite rather than an assumed colour
- [ ] #2 The export-format popup is fixed first and separately verified - at 1.07:1 its text is closer to invisible than the defect TASK-244 was filed for
- [ ] #3 The archived board row is measured inside the live table rather than in a standalone reproduction, since its 2.28:1 light-mode reading came from a detached row and may not hold
- [ ] #4 The guard test added by TASK-244 is extended to cover whichever of these is fixed, so the class cannot silently reappear
<!-- AC:END -->
