---
id: TASK-370
title: Measure safe document generation concurrency before raising its default
status: To Do
assignee: []
created_date: '2026-11-11 15:24'
labels:
  - pipeline
  - performance
dependencies: []
priority: medium
type: spike
ordinal: 370000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Grounded opportunity from Backlog doc-1, Application pipeline efficiency opportunities - 2026-11-11. Historical timings are not a controlled speedup comparison. Preserve TASK-348 all-letter alternatives, TASK-303 model quality/defaults, owner data, cancellation, per-account access and daily budgets. Analysis concurrency and document concurrency are different settings. Document code defaults to one worker; the prior concurrency-five measurement covered fit analyses only. Confirm the active runtime limit and measure one versus two document workers rather than blindly raising analysis concurrency again.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Record the actual running document limit, then compare one and two document workers on a matched workload without changing model/effort or dropping document variants.
- [ ] #2 Record time to first useful package, total throughput, CPU/RAM, provider-limit errors, repairs, cancellations and artifact correctness; label the workload and measurement conditions.
- [ ] #3 Parallel tasks never overwrite each other or cross account/job ownership; shared TeX compilation and same-job variants are explicitly exercised.
- [ ] #4 Keep existing quota retry, pause/resume and daily-budget behavior; stop or recommend a lower value if failures or resource pressure make the higher value unsuitable.
- [ ] #5 Do not raise a default without measured throughput/user-wait benefit and no quality/data-safety regression; document the selected limit or why the experiment rejected a change.
<!-- AC:END -->
