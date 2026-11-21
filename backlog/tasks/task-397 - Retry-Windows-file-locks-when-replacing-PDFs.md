---
id: TASK-397
title: Retry Windows file locks when replacing PDFs
status: Done
assignee: []
created_date: '2026-11-21 09:15'
updated_date: '2026-11-21 09:45'
labels: []
dependencies: []
priority: high
ordinal: 398000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
WinError 32 (file in use) failed 3 runs (1 Adjust, 2 recompiles). Evidence: audits 2026-11-20 (jobs/6526c3ef/tmp audit-reliability.md, audit-intake.md, audit-quality.md). Owner approved 2026-11-21.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Replacing an output file retries briefly (bounded, e.g. 5 x 0.5 s) on PermissionError/WinError 32; a test simulates a transient lock and proves success
- [x] #2 A persistent lock still fails with the existing message
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
PR #438. Running on localhost 2026-11-21 (runtime 03b8d2d, health 200; code presence checked). Transient and persistent PermissionError tests.
<!-- SECTION:NOTES:END -->
