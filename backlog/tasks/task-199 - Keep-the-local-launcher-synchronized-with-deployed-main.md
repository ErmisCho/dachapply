---
id: TASK-199
title: Keep the local launcher synchronized with deployed main
status: To Do
assignee:
  - '@pi'
created_date: '2026-08-29 21:19'
labels:
  - dev-experience
  - deployment
dependencies: []
priority: high
type: task
ordinal: 199000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The normal localhost launcher currently serves whichever branch is checked out in the dirty development worktree, so it can expose code older than the Azure deployment. Make the normal local runtime follow the same origin/main revision as Azure without overwriting active development work.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The normal local launcher serves code from the latest fetched origin/main rather than the active development worktree
- [ ] #2 Updating the local runtime does not reset, clean, or overwrite dirty feature worktrees
- [ ] #3 A fetch or synchronization failure stops startup with a clear message instead of serving stale code
- [ ] #4 Launcher checks cover synchronization and the existing fixed-port cleanup behavior
- [ ] #5 Azure deployment remains sourced from main so local and Azure share the same released code
<!-- AC:END -->
