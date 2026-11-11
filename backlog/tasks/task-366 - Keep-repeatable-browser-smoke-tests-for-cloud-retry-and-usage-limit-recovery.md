---
id: TASK-366
title: Keep repeatable browser smoke tests for cloud retry and usage-limit recovery
status: To Do
assignee: []
created_date: '2026-11-11 14:46'
labels:
  - testing
  - frontend
  - backend
dependencies: []
priority: medium
type: task
ordinal: 366000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
TASK-359/360 were verified using temporary visible-browser harnesses against disposable SQLite/workspaces. Preserve the smallest repeatable checks for those user-facing recovery paths using existing browser tooling. Current npm test runs Vitest; separate frontend/tests browser scripts are not the queue-recovery checks. Reuse established fixtures and scheduler behavior; never require paid model calls, owner credentials, production data or the real CV workspace. A future CI wiring change requires owner approval before merge.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A documented command launches disposable local data/workspace and drives the real frontend and Django routes without paid provider calls or access to owner data.
- [ ] #2 The browser saves/reloads the analysis time limit, observes Finding models with elapsed time, and uses one-time cloud retry without changing the saved cloud-only switch.
- [ ] #3 A simulated provider usage limit renders one short sanitized line; the same task automatically becomes running at an accelerated reset with identical inputs, and the panel cancellation control works.
- [ ] #4 Assertions fail when the load-bearing UI/API recovery behavior is broken; deterministic fixture cancellation and cleanup prevent hanging workers or leftover servers.
- [ ] #5 The checks run repeatably twice on the supported development host and in their intended CI environment; failures retain a concise diagnostic artifact. Any required CI-gate edits are approved before merge.
<!-- AC:END -->
