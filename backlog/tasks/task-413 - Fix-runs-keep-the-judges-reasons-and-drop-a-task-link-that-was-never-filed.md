---
id: TASK-413
title: 'Fix runs: keep the judge''s reasons and drop a task link that was never filed'
status: Done
assignee: []
created_date: '2026-11-25 09:35'
updated_date: '2026-11-25 12:34'
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
- [x] #1 A run the judge refuses keeps the judge's failed criteria on the run, shown on the Failures page
- [x] #2 Judge reasons that repeat private evidence are not kept (same leak check as the PR text)
- [x] #3 A run that ends without a PR shows no task id
- [x] #4 Tests for each are red on the old code and green on the fix
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
PR #458 (1e40e8e), CI green, local suite 2403 passed. New tests red on origin/main in a detached worktree (3 backend, 1 frontend), green on the fix. Codex review: one P2 (older saved runs kept the stale id), fixed in views_failures with a test. Localhost on 1e40e8e (bundle index-DFtsiQ5i.js): /api/failures/ shows task '' for the 10:08 run that had shown TASK-413.
<!-- SECTION:NOTES:END -->
