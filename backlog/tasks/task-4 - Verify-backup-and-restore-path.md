---
id: TASK-4
title: Verify backup and restore path
status: Done
assignee: []
created_date: '2026-06-20 09:50'
updated_date: '2026-06-20 10:00'
labels:
  - P0
  - data
  - backup
  - phase-1
milestone: m-1
dependencies: []
priority: high
ordinal: 4000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Ensure beta user data can be recovered before inviting more users.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Neon/Postgres backup or snapshot process is documented
- [x] #2 App export works for jobs and preferences
- [x] #3 Import restore is tested on a non-production environment
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-06-20 10:00
---
Documented Neon/Postgres backup and restore plan. Existing and new test coverage verifies app export/import paths for jobs/preferences and restore into owned data.
---
<!-- COMMENTS:END -->
