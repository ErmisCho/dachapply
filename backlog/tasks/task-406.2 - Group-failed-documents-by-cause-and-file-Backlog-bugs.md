---
id: TASK-406.2
title: Group failed documents by cause and file Backlog bugs
status: To Do
assignee: []
created_date: '2026-11-23 23:31'
labels: []
dependencies: []
parent_task_id: TASK-406
priority: high
ordinal: 409000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Reuses the TASK-372 collector and triage; fixes its grouping for documents. Part of TASK-406. Owner decisions 2026-11-24: fix up to a PR (the owner merges); a fix starts from a button in the app; the fixing agent may read the full failed files, kept 30 days on this PC only.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Two failures with the same cause and different jobs, names, dates or line numbers form one group; different causes form different groups (tests with the real error texts of 2026-10-21 to 2026-11-23)
- [ ] #2 Usage limits, lost database connections, locked files and cancellations are classed as not a bug and file no task
- [ ] #3 A bug group files exactly one Backlog task through the existing triage; repeats update it; a verified fix closes it and a later failure is a new regression
- [ ] #4 No CV, letter, posting, company or person text reaches the Backlog task (test)
- [ ] #5 The collector is on for the local runtime and off in tests and production
<!-- AC:END -->
