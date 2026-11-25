---
id: TASK-414
title: 'Fix runs: a run that ends without a PR still puts its bug on the board'
status: Done
assignee: []
created_date: '2026-11-25 12:34'
updated_date: '2026-11-25 13:26'
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
- [x] #1 A run that ends failed or stopped opens one PR whose diff is only the new backlog task file, with fixed wording (no evidence text)
- [x] #2 The group shows that task id while that PR is open; a later run reuses it instead of filing a second task
- [x] #3 A run that opens a fix PR does not also open a backlog-only PR
- [x] #4 Tests red on the old code, green on the fix
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
PR #461 (3e53962), CI green; test_fix_runs + test_failures_page 70 passed. Implementer (sonnet) built it; review added: the task file must match what triage wrote (the agent can edit the worktree, and this PR skips the diff checks), and a linked id must carry the group marker (the real rerun on 2026-11-25 followed a stale TASK-413 link and opened #462 for the wrong task; closed). Codex, 3 rounds: wrong branch on a 3rd run, stopped run never refreshed, stale open state, task already on main, failed lookup: all fixed with tests. Declined: id collision across groups (one run at a time; check_active_branches on). Localhost on 3e53962.
<!-- SECTION:NOTES:END -->
