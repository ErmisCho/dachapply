---
id: TASK-406.4
title: Start a fix run from the app that ends in a PR
status: In Progress
assignee: []
created_date: '2026-11-23 23:31'
updated_date: '2026-11-25 09:51'
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
- [x] #1 Fix starts only for the owner, from the local machine, one run at a time, and only when enabled in .env; otherwise the button is off and says why
- [x] #2 The run works in its own worktree from origin/main and never merges, deploys, migrates, pushes to main or touches the CV workspace; the agent itself has no push, gh or network tool, the app pushes and opens the PR
- [x] #3 The prompt gives the Backlog task, requires a sealed rubric before code, a test that fails first, ponytail and an asian-dad verdict; the PR body carries the verdict and the test result
- [x] #4 No PR is opened when tests fail, the diff is empty, or the diff contains text from the evidence (test for each)
- [x] #5 A run can be stopped and has a time limit; a restart leaves it marked interrupted, not running
- [x] #6 The agent treats evidence as data: an instruction planted in a failed file is not followed (test run with a planted instruction)
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Design constraints found 2026-11-24: evidence contains posting and model text, so it is untrusted input to the agent; the app, not the agent, pushes and opens the PR; abort when the diff contains evidence text; the Fix run calls triage(operation, root=worktree) so the bug file lands in the PR. First real case: job 2095 on 2026-11-23, the model returned a bare letter body three times although the source letters are valid LaTeX.

PR #446 (2041aa9). Real agent on a disposable clone with invented evidence and a planted instruction: two runs, neither followed it. Run 1 was stopped from the page and left nothing behind; run 2 ended failed with no PR because the judge refused it (the agent had removed an existing test case after the suite failed). Both before the fixes in e8c523f (stop gap, red means assertion, flaky rerun). Not seen yet: a run that ends in a real GitHub PR. Residual risk: the app runs agent-written tests as the owner. FIX_RUNS_ENABLED=1 on localhost since 2026-11-24 (owner decision).

First real run from the app 2026-11-25 (run 20261125-100850-9c43, 24 min): plan, implement, checks passed, red check failed on old code as required, 2402 backend tests passed, then the judge (opus) answered FAILURE and no PR was opened. Its reasons were not kept and the page showed a task id that never existed; both fixed in TASK-413. Still open: a run that ends in a real GitHub PR.
<!-- SECTION:NOTES:END -->
