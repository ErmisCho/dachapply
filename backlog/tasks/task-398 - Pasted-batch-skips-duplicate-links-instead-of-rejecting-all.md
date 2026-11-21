---
id: TASK-398
title: Pasted batch skips duplicate links instead of rejecting all
status: To Do
assignee: []
created_date: '2026-11-21 09:15'
labels: []
dependencies: []
priority: high
ordinal: 399000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
One duplicate link in a multi-link paste returns 400 'Nothing was added yet' for the whole batch (views.py bulk_create_jobs). Evidence: audits 2026-11-20 (jobs/6526c3ef/tmp audit-reliability.md, audit-intake.md, audit-quality.md). Owner approved 2026-11-21.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A multi-link batch with one duplicate adds the others and reports the duplicate as skipped (test)
- [ ] #2 A single duplicate link still shows the existing duplicate prompt
<!-- AC:END -->
