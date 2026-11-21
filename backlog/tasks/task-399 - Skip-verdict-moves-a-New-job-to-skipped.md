---
id: TASK-399
title: Skip verdict moves a New job to skipped
status: Done
assignee: []
created_date: '2026-11-21 09:15'
updated_date: '2026-11-21 09:45'
labels: []
dependencies: []
priority: high
ordinal: 400000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
A New job evaluated as skip stays New for up to 30 days. Evidence: audits 2026-11-20 (jobs/6526c3ef/tmp audit-reliability.md, audit-intake.md, audit-quality.md). Owner approved 2026-11-21.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Creating an evaluation with verdict skip for a job in status new sets its status to skipped (test); other statuses are not changed
- [x] #2 Board no longer lists such a job under New
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
PR #440. Running on localhost 2026-11-21 (runtime 03b8d2d, health 200; code presence checked). Skipped status removes the job from New.
<!-- SECTION:NOTES:END -->
