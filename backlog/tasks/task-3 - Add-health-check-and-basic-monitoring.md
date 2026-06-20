---
id: TASK-3
title: Add health check and basic monitoring
status: To Do
assignee: []
created_date: '2026-06-20 09:50'
updated_date: '2026-06-20 09:59'
labels:
  - P0
  - backend
  - ops
  - phase-1
milestone: m-1
dependencies: []
priority: high
ordinal: 3000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Add a lightweight production health signal and make downtime easier to detect.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Unauthenticated /api/health/ endpoint returns app and database status
- [x] #2 Health check does not expose secrets or user data
- [ ] #3 Deployment platform or external monitor checks the endpoint
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-06-20 09:59
---
Added public /api/health/ endpoint with database probe and safe response shape. Added test. External monitor setup remains platform-dependent.
---
<!-- COMMENTS:END -->
