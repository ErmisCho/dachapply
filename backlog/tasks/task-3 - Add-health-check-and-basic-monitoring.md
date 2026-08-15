---
id: TASK-3
title: Add health check and basic monitoring
status: Done
assignee:
  - '@claude'
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

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Added .github/workflows/uptime-monitor.yml: probes /api/health/ every 30 minutes and on demand,
failing the run when the app is unreachable or reports unhealthy, which GitHub notifies by email.

Before this, the only check was the post-deploy curl inside the deploy workflow. That catches a
broken release but says nothing about the hours between deploys, so a database outage or crashed
revision would have been found only on the next manual visit.

Three attempts with a 20s gap, because a single blip during a Container Apps revision swap is not
an outage. jobradar.views.health:63-75 already answers 503 with {"status":"degraded",
"database":"unavailable"} when Postgres is unreachable, so `curl --fail` catches that on its own;
the body assertion is a second line of defence in case the endpoint is ever changed to answer 200
while degraded. The URL falls back to a default but can be overridden with the APP_URL repository
variable, so a hostname change needs no code edit.
<!-- SECTION:NOTES:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Unauthenticated /api/health/ endpoint returns app and database status
- [x] #2 Health check does not expose secrets or user data
- [x] #3 Deployment platform or external monitor checks the endpoint
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-06-20 09:59
---
Added public /api/health/ endpoint with database probe and safe response shape. Added test. External monitor setup remains platform-dependent.
---
<!-- COMMENTS:END -->
