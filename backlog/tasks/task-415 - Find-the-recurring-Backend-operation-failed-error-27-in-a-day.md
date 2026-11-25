---
id: TASK-415
title: Find the recurring 'Backend operation failed' error (27 in a day)
status: To Do
assignee: []
created_date: '2026-11-25 12:34'
labels: []
dependencies: []
priority: medium
ordinal: 419000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The error collector holds 27 occurrences of one backend error group (operation 39ec6ac5...) from 2026-11-24 09:45 to 2026-11-25 09:57 UTC, with no traceback. One of them was an HTTP 500 on DELETE /api/jobs/2104/ that returned the expected 400 on retry. Find the cause from the occurrence data and server logs, fix it with a test.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The cause is named with the evidence that shows it
- [ ] #2 A test reproduces it red, then green on the fix
- [ ] #3 After the fix, no new occurrence of that group for one day of normal use (checked from the collector)
<!-- AC:END -->
