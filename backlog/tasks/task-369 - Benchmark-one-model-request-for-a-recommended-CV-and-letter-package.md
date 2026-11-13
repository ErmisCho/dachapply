---
id: TASK-369
title: Benchmark one model request for a recommended CV and letter package
status: To Do
assignee: []
created_date: '2026-11-11 15:24'
updated_date: '2026-11-13 07:08'
labels:
  - pipeline
  - performance
dependencies: []
priority: medium
type: spike
ordinal: 369000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Grounded opportunity from Backlog doc-1, Application pipeline efficiency opportunities - 2026-11-11. Historical timings are not a controlled speedup comparison. Preserve TASK-348 all-letter alternatives, TASK-303 model quality/defaults, owner data, cancellation, per-account access and daily budgets. Automatic document preparation launches CV and letter variants separately even though the existing generator supports both together. Compare that existing combined capability with separate requests for the useful recommended package; keep all alternative letters and independent artifact/review semantics.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Compare combined versus separate CV/letter generation on the same representative jobs, templates, model/effort and candidate evidence, recording requests, elapsed time, repairs and manual corrections.
- [ ] #2 A resulting package meets existing CV/letter page, language, layout and factual-accuracy requirements; a lower request count alone is not accepted as an improvement.
- [ ] #3 All requested alternative letter templates remain available and distinguishable; copy selection, final-package selection, ownership and filenames remain correct.
- [ ] #4 A failure/cancel in the combined path does not erase or overwrite independently usable artifacts or owner-reviewed files; retries do not regenerate already valid unrelated variants without reason.
- [ ] #5 Retain current behavior unless the controlled comparison shows a benefit without a quality regression; record a negative finding rather than shipping an unproven change.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Implement isolated package experiment using existing planning, generation and repair services; preserve all alternative variants and ready artifacts. Add owner comparison report and hermetic tests, then run required checks without changing status or acceptance boxes.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
TASK-369: Added benchmark_package experiment with separate/combined arms, isolated arm workspaces, existing template planning and generator validation/compilation/repair, independent alternative letters, ready-variant retry reuse, and failure/cancellation preservation. Added registry/report hook and side-by-side owner review.md with PDF pages, required language, metrics, quality checklist and manual correction fields. Added fake-provider/compiler contract coverage and package usage documentation. Production entry points and defaults remain unchanged.
<!-- SECTION:NOTES:END -->
