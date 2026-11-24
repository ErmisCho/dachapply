---
id: TASK-410
title: 'Fix runs: Codex writes the fix, Claude judges it'
status: In Progress
assignee: []
created_date: '2026-11-24 15:05'
updated_date: '2026-11-24 15:10'
labels: []
dependencies: []
priority: high
ordinal: 415000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner decision 2026-11-24 ('Codex implements, Claude verifies'): in services/fix_runs.py the plan, implement and repair calls use the Codex CLI; the judge stays a separate Claude call. All existing gates stay.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 plan, implement and repair run codex exec; judge runs claude; tests prove both argument lists
- [ ] #2 Codex can write only its worktree and the work folder, has no network, and cannot read a file outside them; or, if its sandbox cannot stop reading, that is measured, documented and the diff checks cover it
- [ ] #3 Every existing check and test of fix_runs still passes; no other file changes except docs and tests
- [ ] #4 A real codex exec call on a throwaway folder shows the limits of AC2
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Route implementation stages to Codex and retain the Claude judge and existing gates. 2. Guard added text against local credential contents and provide a manual sandbox probe. 3. Update hermetic tests and documentation; run the requested test suite.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implementation prepared. Requested pytest command could not run: uv default cache access denied; with workspace cache, pytest temporary directories also fail with Windows access denied. Sandbox probe intentionally not run at user request. Task remains In Progress.
<!-- SECTION:NOTES:END -->
