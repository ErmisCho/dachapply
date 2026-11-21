---
id: TASK-395
title: Generation results survive a DB connection drop at save
status: To Do
assignee: []
created_date: '2026-11-21 09:14'
labels: []
dependencies: []
priority: high
ordinal: 396000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
4 finished generations (115-619 s of model work) were discarded because the DB connection dropped when saving the result. Evidence: audits 2026-11-20 (jobs/6526c3ef/tmp audit-reliability.md, audit-intake.md, audit-quality.md). Owner approved 2026-11-21.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 When saving a finished task result raises a DB connection error, the connection is closed and the save retried once, without re-running the model (test simulates the drop)
- [ ] #2 A second failure reports the error as today
<!-- AC:END -->
