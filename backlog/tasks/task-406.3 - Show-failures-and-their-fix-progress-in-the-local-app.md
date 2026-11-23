---
id: TASK-406.3
title: Show failures and their fix progress in the local app
status: To Do
assignee: []
created_date: '2026-11-23 23:31'
labels: []
dependencies: []
parent_task_id: TASK-406
priority: high
ordinal: 410000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner-only, local only. Part of TASK-406. Owner decisions 2026-11-24: fix up to a PR (the owner merges); a fix starts from a button in the app; the fixing agent may read the full failed files, kept 30 days on this PC only.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 An owner-only page lists the groups with cause, count, last time, class, Backlog task, and state (new, running, PR open, merged, failed, not a bug)
- [ ] #2 Opening a group shows its records with error, diagnostics and the saved files; any other account and production get 404
- [ ] #3 The page shows the running fix live: current step, elapsed time and the last lines of its log, and the final result with the PR link
- [ ] #4 Verified in a real browser on localhost, light and dark, at 360 px and desktop
<!-- AC:END -->
