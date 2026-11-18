---
id: TASK-388
title: Compile errors get one automatic repair pass
status: To Do
assignee: []
created_date: '2026-11-18 22:38'
labels: []
dependencies: []
priority: high
ordinal: 389000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
On a LaTeX compile failure in generation or full-optimization Adjust, feed the error lines from the log to one automatic repair pass before failing. Evidence: adjustments.jsonl 2026-10-21..11-18, 130 Adjusts over 34 jobs (median 3 ready Adjusts/job); audits in jobs/6526c3ef/tmp (optimization-audit.md, ux-audit.md). Owner approved 2026-11-18.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A test simulates a first compile failure and proves exactly one repair attempt with the log's error lines in the prompt
- [ ] #2 If the repair compiles, the run ends ready and the report says a compile error was repaired; if not, the original failure is reported and the failed .tex/.log are kept as today (TASK-334)
- [ ] #3 Exact/literal Adjust routes (no AI) do not call the model on compile failure
<!-- AC:END -->
