---
id: TASK-408
title: Stop the analysis-lane tests from failing on a database lock
status: In Progress
assignee: []
created_date: '2026-11-24 12:24'
updated_date: '2026-11-24 14:06'
labels: []
dependencies: []
priority: medium
type: bug
ordinal: 413000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
test_analysis_lanes tests fail with 'database table is locked' (jobradar_jobevaluation, jobradar_userprofile) on slow runs: twice in CI on 2026-11-24 (run 45389522628, attempts 1 and 2, 383 s and 452 s) and once locally under load; they pass alone and on normal runs. Threads share one in-memory sqlite database.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The cause is named with evidence
- [x] #2 The two tests pass 20 times in a row under CPU load
- [x] #3 No test is skipped or retried to hide it
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Cause: the test database is one in-memory SQLite in shared-cache mode; a thread reading a table another writes gets SQLITE_LOCKED at once (no timeout applies), shown with a two-connection demo. Fix: readers take no table locks (PRAGMA read_uncommitted in tests/conftest.py). Measured: old code 2 of 9 loaded runs failed; new code 0 of 23 loaded runs (40 busy processes on 24 cores); full suite 2401 passed. A WAL file database was tried and rejected: 195 tests need worker threads to see the test's unsaved rows. Test setup only; no production code changed.
<!-- SECTION:NOTES:END -->
