---
id: TASK-406.1
title: Save the evidence of every failed document
status: To Do
assignee: []
created_date: '2026-11-23 23:31'
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
- [ ] #1 Every failed document task (generate, readjust, recompile, preparation) leaves one record with time, job id, route, model, error and diagnostics
- [ ] #2 Its record keeps the TeX and LaTeX log of each failed compile and the model answer of each rejected attempt, also when no LaTeX ran
- [ ] #3 Cancelled tasks and scheduled usage-limit retries leave no record; a retry that then fails does
- [ ] #4 Records older than 30 days are deleted; a record never goes into git, Backlog, an export or a public response
- [ ] #5 A failure while saving never changes the task result (test)
<!-- AC:END -->
