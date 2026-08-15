---
id: TASK-61
title: >-
  Improve CV generation controls, feedback, revision speed, and artifact
  visibility
status: Done
assignee:
  - '@claude'
created_date: '2026-08-13 19:30'
updated_date: '2026-08-15 14:35'
labels:
  - cv-generation
  - ux
  - performance
dependencies: []
priority: high
ordinal: 62000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Track the remaining CV-generation usability and performance problems: provider/model capability controls, transparent phase progress, instruction-faithful fast revisions, realistic time estimates, and visible filesystem paths for source and generated artifacts.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Each reported concern is covered by a focused child task with testable acceptance criteria
- [x] #2 The child tasks can be delivered independently without losing the shared CV-generation context
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
AC1 was only genuinely true from 2026-08-14. Until then TASK-61.4 AC4 ('a clickable open action where the local browser/platform supports it') had no testable threshold and was the documented counterexample to this criterion; TASK-64 restated it as a closed-key Reveal endpoint, which is binary-checkable, and it is now implemented. AC2 held throughout: 61.1-61.4 were each delivered and verified on their own.

CLOSED 2026-08-15. All four children are Done. The last two criteria were settled by eight live provider runs rather than by argument:
- TASK-61.2 AC6 - cv-benchmarks.jsonl now records estimated vs actual and per-phase timings. The benchmark immediately exposed that revision_factor was inverted (revisions are ~1.6x slower than generations, not 45% faster), so estimates had been ~2x optimistic - the exact complaint 61.2 was opened for. Recalibrated to within 7%.
- TASK-61.3 AC5 - reworded under TASK-66. The 30s threshold was unreachable: app-side cost is 2.56-6.02s while the provider round-trip is 50.5-161.9s, so no app-side change could satisfy it. Restated against measurement, and the underlying goal was met anyway - simple revisions went from the 5-7 minutes that opened the task to 96-120s at default settings.

Two production defects surfaced only because the work was exercised live, both fixed under 61.3: revisions failed outright after ~5 minutes on a stale Neon connection (generation was immune, so no test caught it), and the ETA miscalibration above.

Spun out and closed: TASK-62 (test isolation), TASK-63 (artifact-path rehydration), TASK-64 (AC4 rewording), TASK-66 (AC5 recalibration). Still open: TASK-65 (migrate Docker/CI to uv), which is infrastructure and independent of this family.
<!-- SECTION:NOTES:END -->
