---
id: TASK-400
title: Duplicate check by company and title
status: To Do
assignee: []
created_date: '2026-11-21 09:15'
labels: []
dependencies: []
priority: high
ordinal: 401000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Duplicates are detected only by exact URL; the same posting from another board or URL variant is added twice. Evidence: audits 2026-11-20 (jobs/6526c3ef/tmp audit-reliability.md, audit-intake.md, audit-quality.md). Owner approved 2026-11-21.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Adding a job whose normalized company+title matches an existing job of the same user is reported as a possible duplicate the same way a URL duplicate is (test)
- [ ] #2 Different titles at the same company are not flagged
<!-- AC:END -->
