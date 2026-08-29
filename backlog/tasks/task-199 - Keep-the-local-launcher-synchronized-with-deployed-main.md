---
id: TASK-199
title: Keep the local launcher synchronized with deployed main
status: In Progress
assignee:
  - '@pi'
created_date: '2026-08-29 21:19'
updated_date: '2026-08-29 21:45'
labels:
  - dev-experience
  - deployment
dependencies: []
modified_files:
  - scripts/dachapply-local-runtime.cmd
  - backend/jobradar/tests/test_local_runtime_launcher.py
  - ../Configuration/bin/dachapply-start.cmd
  - ../Configuration/test.cmd
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

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Keep Azure's existing tested main-branch deployment unchanged. 2. Change the normal Windows launcher to fetch origin/main and prepare a dedicated detached runtime worktree, failing closed before server startup if synchronization fails. 3. Link only the existing ignored .env into that runtime and install locked dependencies there; never reset or clean the development worktree. 4. Extend the launcher smoke check for synchronization, fail-closed behavior, and fixed-port cleanup. 5. Verify runtime/main commit equality and unchanged dirty-worktree status, then merge and restart localhost from the release runtime.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Root cause research: Azure already builds and deploys each tested main push by immutable github.sha. The normal local launcher instead hard-codes the dirty development worktree, currently nine commits behind origin/main. The launcher is a machine-local Configuration/bin file (same precedent as TASK-58), so the minimal safe fix is a separate disposable release worktree rather than pulling or resetting active work.

Implemented a dedicated  worktree. The machine launcher stops existing local servers, fetches origin/main, loads the runtime script from that exact ref, synchronizes only the disposable runtime, links the existing ignored .env, installs locked dependencies, and starts Django/Vite there. Any fetch, script-load, ref mismatch, env-link, or dependency failure exits nonzero without serving stale code.

Validation: prepare-only runtime HEAD and origin/main both resolved to bbc7232ec7a5b484ab3b24163063f104df8914c6; the dirty development worktree status hash was unchanged before/after; an invalid source exited 1 with no runtime created; Configuration/test.cmd passed all checks; 1027 backend and 193 frontend tests plus the production build passed.

The dedicated runtime path omitted in the preceding shell-rendered note is `%LOCALAPPDATA%\dachapply\main-runtime`.
<!-- SECTION:NOTES:END -->
