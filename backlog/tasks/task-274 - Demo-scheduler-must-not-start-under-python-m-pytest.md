---
id: TASK-274
title: Demo scheduler must not start under python -m pytest
status: Done
assignee: []
created_date: '2026-10-07 18:00'
labels:
  - backend
  - tests
dependencies: []
priority: high
ordinal: 271000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found while verifying TASK-273. Full backend runs on the owner's machine failed different mailbox tests on each run: 21 failures, then 0, then 30. Every failing test passed in isolation and in its own file. The first failure under `-x` was `test_a_run_that_crashes_midway_loses_nothing_and_resumes`, which saw extra MailboxMessage uids 2000000000, 2000000001 and 2000000002. Those are demo_data.py's `first_uid`.

Root cause: `demo_scheduler._should_start_scheduler` detects a test run from argv. `python -m pytest` has argv[0] == `__main__.py` and no `pytest` argument, so the daemon thread started during the tests. After the daily RUN_AT it seeded demo mail into the test database mid-run. CI runs plain `pytest` and never hit this.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The scheduler does not start when pytest is loaded, however it was launched
- [x] #2 A test reproduces the `python -m pytest` argv and fails without the fix
- [x] #3 A full `python -m pytest` run on the owner's machine after RUN_AT has 0 failures
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
- `_should_start_scheduler` returns False when `'pytest' in sys.modules`, before the argv checks.
- test_demo_scheduler_gate.py sets argv to `.../pytest/__main__.py -q`. It passes with the fix and fails without it (mutation run).
- A full `python -m pytest` run at 17:49–17:58, after the scheduler's daily start time: 1369 passed, 0 failed. Earlier runs the same way had 21 and 30 failures.
<!-- SECTION:NOTES:END -->
