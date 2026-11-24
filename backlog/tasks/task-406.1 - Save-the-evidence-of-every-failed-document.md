---
id: TASK-406.1
title: Save the evidence of every failed document
status: In Progress
assignee: []
created_date: '2026-11-23 23:31'
updated_date: '2026-11-24 06:39'
labels: []
dependencies: []
parent_task_id: TASK-406
priority: high
ordinal: 408000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Failed generations, readjusts and recompiles of CVs, letters and messages. Part of TASK-406. Owner decisions 2026-11-24: fix up to a PR (the owner merges); a fix starts from a button in the app; the fixing agent may read the full failed files, kept 30 days on this PC only.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Every failed document task (generate, readjust, recompile, preparation) leaves one record with time, job id, route, model, error and diagnostics
- [x] #2 Its record keeps the TeX and LaTeX log of each failed compile and the model answer of each rejected attempt, also when no LaTeX ran
- [x] #3 Cancelled tasks and scheduled usage-limit retries leave no record; a retry that then fails does
- [x] #4 Records older than 30 days are deleted; a record never goes into git, Backlog, an export or a public response
- [x] #5 A failure while saving never changes the task result (test)
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
PR #444 (1ac2603), CI green. Localhost runtime on 1ac2603 since 2026-11-24, health 200; collector on (private folder outside the checkouts, ACL owner/admins/SYSTEM), 0 occurrences so far. Hooks shown red on the old code; Codex findings fixed. Open: no real failure has gone through it on localhost yet.
<!-- SECTION:NOTES:END -->
