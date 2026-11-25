---
id: TASK-414
title: 'Fix runs: a run that ends without a PR still puts its bug on the board'
status: To Do
assignee: []
created_date: '2026-11-25 12:34'
labels: []
dependencies: []
priority: medium
ordinal: 418000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner decision 2026-11-25. Today a Fix run files the bug task inside its own worktree, so the task reaches main only with a fix PR; a refused run (first real run, 2026-11-25) left the actionable group with no Backlog bug. When a run ends without a PR, the app opens a backlog-only PR that contains just that task file, for the owner to merge.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A run that ends failed or stopped opens one PR whose diff is only the new backlog task file, with fixed wording (no evidence text)
- [ ] #2 The group shows that task id while that PR is open; a later run reuses it instead of filing a second task
- [ ] #3 A run that opens a fix PR does not also open a backlog-only PR
- [ ] #4 Tests red on the old code, green on the fix
<!-- AC:END -->
