---
id: TASK-408
title: Stop the analysis-lane tests from failing on a database lock
status: To Do
assignee: []
created_date: '2026-11-24 12:24'
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
- [ ] #1 The cause is named with evidence
- [ ] #2 The two tests pass 20 times in a row under CPU load
- [ ] #3 No test is skipped or retried to hide it
<!-- AC:END -->
