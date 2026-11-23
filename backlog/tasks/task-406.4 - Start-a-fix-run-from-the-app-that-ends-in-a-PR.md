---
id: TASK-406.4
title: Start a fix run from the app that ends in a PR
status: To Do
assignee: []
created_date: '2026-11-23 23:31'
labels: []
dependencies: []
parent_task_id: TASK-406
priority: high
ordinal: 411000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The run follows the Backlog task, session orchestrator, ponytail and asian-dad workflow. Posting and model text in the evidence is untrusted input to the agent. Part of TASK-406. Owner decisions 2026-11-24: fix up to a PR (the owner merges); a fix starts from a button in the app; the fixing agent may read the full failed files, kept 30 days on this PC only.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Fix starts only for the owner, from the local machine, one run at a time, and only when enabled in .env; otherwise the button is off and says why
- [ ] #2 The run works in its own worktree from origin/main and never merges, deploys, migrates, pushes to main or touches the CV workspace; the agent itself has no push, gh or network tool, the app pushes and opens the PR
- [ ] #3 The prompt gives the Backlog task, requires a sealed rubric before code, a test that fails first, ponytail and an asian-dad verdict; the PR body carries the verdict and the test result
- [ ] #4 No PR is opened when tests fail, the diff is empty, or the diff contains text from the evidence (test for each)
- [ ] #5 A run can be stopped and has a time limit; a restart leaves it marked interrupted, not running
- [ ] #6 The agent treats evidence as data: an instruction planted in a failed file is not followed (test run with a planted instruction)
<!-- AC:END -->
