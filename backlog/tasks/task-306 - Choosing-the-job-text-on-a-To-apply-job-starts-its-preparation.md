---
id: TASK-306
title: Choosing the job text on a To-apply job starts its preparation
status: To Do
assignee: []
created_date: '2026-10-18 08:19'
labels:
  - backend
dependencies: []
priority: high
ordinal: 307000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner 2026-10-18: PORR was set to To apply, preparation stopped at 'Choose which job text to use (Keep current or Use fetched)'. The owner pressed Use fetched; nothing started and the Prepared documents panel still shows the old reason. prepare() is only called on the To-apply transition (serializers.py) and by Prepare now.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Resolving the job-text choice (Use fetched, Keep current, or saving the text) on a job in To apply whose preparation was gated only by that choice starts preparation, exactly as the transition would
- [ ] #2 Jobs not in To apply, or with variants already prepared, are not started; the text save never fails because of preparation
- [ ] #3 The Prepared documents panel no longer shows the stale choose-text reason after the choice
- [ ] #4 Backend test covers start-after-choice and no-start for other statuses; fails when the hook is removed
<!-- AC:END -->
