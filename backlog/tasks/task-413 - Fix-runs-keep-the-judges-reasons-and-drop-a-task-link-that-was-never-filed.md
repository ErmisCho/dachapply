---
id: TASK-413
title: 'Fix runs: keep the judge''s reasons and drop a task link that was never filed'
status: Done
assignee: []
created_date: '2026-11-25 09:35'
labels: []
dependencies: []
priority: medium
ordinal: 417000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found by the first real Fix run on localhost (2026-11-25, run 20261125-100850-9c43): the judge refused the diff and the page only said 'The judge verdict was FAILURE, not PERFECT.', so nobody can tell why; and the group showed TASK-413, a task that only existed in the deleted fix worktree.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A run the judge refuses keeps the judge's failed criteria on the run, shown on the Failures page
- [ ] #2 Judge reasons that repeat private evidence are not kept (same leak check as the PR text)
- [ ] #3 A run that ends without a PR shows no task id
- [ ] #4 Tests for each are red on the old code and green on the fix
<!-- AC:END -->
