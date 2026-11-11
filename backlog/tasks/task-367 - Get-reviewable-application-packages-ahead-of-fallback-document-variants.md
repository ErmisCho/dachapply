---
id: TASK-367
title: Get reviewable application packages ahead of fallback document variants
status: To Do
assignee: []
created_date: '2026-11-11 15:24'
labels:
  - pipeline
  - performance
dependencies: []
priority: medium
type: enhancement
ordinal: 367000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Grounded opportunity from Backlog doc-1, Application pipeline efficiency opportunities - 2026-11-11. Historical timings are not a controlled speedup comparison. Preserve TASK-348 all-letter alternatives, TASK-303 model quality/defaults, owner data, cancellation, per-account access and daily budgets. The automatic preparation queue appends all variants of one job to a shared FIFO. Extra alternatives can sit ahead of the next job first useful CV/letter package. Improve time to useful packages across jobs without discarding requested alternatives or pretending total model work has disappeared.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A repeatable multi-job workload measures baseline and resulting time to first/next reviewable CV plus required/recommended letter package, as well as total batch completion.
- [ ] #2 Useful packages are not unnecessarily delayed behind other jobs fallback variants; all applicable requested alternatives are still enqueued and eventually produced.
- [ ] #3 Owner Move-to-front actions, cancellation/retry, restart recovery, account isolation and daily limits retain their documented behavior.
- [ ] #4 Queue ordering/progress/ETA describe the actual scheduling; a focused regression test demonstrates the changed scheduling rather than only checking metadata.
- [ ] #5 Ship a scheduling change only with measured first-package improvement and no missing required documents or lost alternatives; otherwise record the rejected approach and evidence.
<!-- AC:END -->
