---
id: TASK-394
title: Fit analysis runs at medium effort
status: In Progress
assignee: []
created_date: '2026-11-21 09:14'
updated_date: '2026-11-21 09:45'
labels: []
dependencies: []
priority: high
ordinal: 395000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The automatic fit analysis always runs at effort high: 254 runs, 74 s median since 2026-10-20 (cv-benchmarks.jsonl). Evidence: audits 2026-11-20 (jobs/6526c3ef/tmp audit-reliability.md, audit-intake.md, audit-quality.md). Owner approved 2026-11-21.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The automatic fit analysis requests effort medium (code + test); the user's explicit choice elsewhere is unchanged
- [ ] #2 Median fit duration over the next 20 runs is at most 45 s (measured from benchmarks after deploy; may stay open until measured)
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
PR #437. Running on localhost 2026-11-21 (runtime 03b8d2d, health 200; code presence checked). Blocker for AC2: needs 20 real automatic fit runs after 2026-11-21 in cv-benchmarks.jsonl to measure the median.
<!-- SECTION:NOTES:END -->
