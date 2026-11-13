---
id: TASK-370
title: Measure safe document generation concurrency before raising its default
status: Done
assignee: []
created_date: '2026-11-11 15:24'
updated_date: '2026-11-12 17:37'
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
- [x] #1 Record the actual running document limit, then compare one and two document workers on a matched workload without changing model/effort or dropping document variants.
- [ ] #2 Record time to first useful package, total throughput, CPU/RAM, provider-limit errors, repairs, cancellations and artifact correctness; label the workload and measurement conditions.
- [x] #3 Parallel tasks never overwrite each other or cross account/job ownership; shared TeX compilation and same-job variants are explicitly exercised.
- [x] #4 Keep existing quota retry, pause/resume and daily-budget behavior; stop or recommend a lower value if failures or resource pressure make the higher value unsuitable.
- [x] #5 Do not raise a default without measured throughput/user-wait benefit and no quality/data-safety regression; document the selected limit or why the experiment rejected a change.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Add read-only fixture export and isolated sqlite runner with an extensible experiment registry. 2. Instrument real queue/model services and validate artifacts and metrics. 3. Add hermetic boundary-fake tests, commands documentation, and run required checks. Real measurements remain for coordinator; defaults unchanged.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Built a shared benchmark service and benchmark_export / benchmark_run management commands. Export uses owner-scoped values/get SELECTs in a rolled-back transaction, an input-file allowlist, and repository-output rejection. Runner requires empty scratch sqlite, copies inputs to a fresh system-temp workspace, preserves model/effort and all document variants, and registers concurrency through an extensible experiment dict. Added request/repair/error timing, CPU/RAM sampling, artifact hashes/pages and ownership/overwrite checks, JSON/Markdown reports, hermetic queue and real-generator boundary tests, and docs/benchmarks.md commands. Production defaults and task acceptance/status remain unchanged; real matched measurements and manual quality review are for the coordinator.

2026-11-13 result (real models, gpt-6.1-sol high, 5 exported jobs, scratch sqlite + temp workspace, Windows 11 host):
- 1 worker (the running default, PREP_QUEUE_CONCURRENCY=1): first useful package 523 s, total 1088 s, 5 documents ready, 0 provider-limit errors, 1 repair, no overwrites.
- 2 workers: first useful package 479 s, total 675 s, 4 documents ready; three model calls started together and each slowed 2-3x (300-475 s vs 18-150 s), so one requirements analysis hit the 5-minute limit and that job's documents were lost. No overwrites.
- Decision (owner, 2026-11-13): keep 1 document at a time; default unchanged. Revisit only if the provider handles parallel calls faster.
- AC2 gap: CPU/RAM were not recorded (psutil unavailable); owner chose to close without re-running.
<!-- SECTION:NOTES:END -->
