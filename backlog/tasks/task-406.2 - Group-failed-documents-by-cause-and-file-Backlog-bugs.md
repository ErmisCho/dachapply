---
id: TASK-406.2
title: Group failed documents by cause and file Backlog bugs
status: Done
assignee: []
created_date: '2026-11-23 23:31'
updated_date: '2026-11-25 09:50'
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
- [x] #1 Two failures with the same cause and different jobs, names, dates or line numbers form one group; different causes form different groups (tests with the real error texts of 2026-10-21 to 2026-11-23)
- [x] #2 Usage limits, lost database connections, locked files and cancellations are classed as not a bug and file no task
- [x] #3 A bug group files exactly one Backlog task through the existing triage; repeats update it; a verified fix closes it and a later failure is a new regression
- [x] #4 No CV, letter, posting, company or person text reaches the Backlog task (test)
- [x] #5 The collector is on for the local runtime and off in tests and production
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
PR #444 (1ac2603), CI green. Localhost runtime on 1ac2603 since 2026-11-24, health 200; collector on (private folder outside the checkouts, ACL owner/admins/SYSTEM), 0 occurrences so far. Hooks shown red on the old code; Codex findings fixed. Open: no real failure has gone through it on localhost yet. Triage must run with root=<fix worktree> (the runtime is a detached checkout, so a task file written there would be lost); operation=failure_evidence.signature(...).

Verified for real 2026-11-25: /api/failures/ showed the two failures as two groups, 'Select a CV template' (class unknown, state look, no task) and 'LaTeX could not compile the document: Undefined control sequence (line N)' (class actionable, state new). The Fix run filed the bug in its worktree as designed; because the judge refused the run, that task file went with the worktree while the page still showed its id. Fixed in TASK-413.
<!-- SECTION:NOTES:END -->
