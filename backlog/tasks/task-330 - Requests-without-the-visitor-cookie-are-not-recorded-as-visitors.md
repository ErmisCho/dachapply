---
id: TASK-330
title: Requests without the visitor cookie are not recorded as visitors
status: Done
assignee: []
created_date: '2026-10-21 14:05'
updated_date: '2026-10-22 13:26'
labels:
  - backend
dependencies: []
priority: high
ordinal: 330000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner 2026-10-21: Neon alert 'dachapply-production has used 100% of its monthly 5 GB network transfer'. Measured read-only on production: jobradar_sitevisitor holds 371,715 rows (115 MB) and visitordailyusage 371,926 (68 MB); ~43,000 new visitors per day on Oct 19/20, since at least Oct 2. Localhost log: 5,860 GET / today at exactly 2 s intervals; captured headers show a WebSocket upgrade to ws://127.0.0.1:8000/ with no cookie, no Origin, no User-Agent, from the owner's main Chrome profile. UserUsageMiddleware mints a new visitor id for every cookieless request and records it (~8-10 DB round trips each). Owner chose: stop counting cookieless hits.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A request that arrives without the visitor cookie gets the cookie but writes no usage rows (no SiteVisitor, VisitorDailyUsage, SiteDailyUsage or UserDailyUsage change, no DB query for usage)
- [x] #2 A request that carries the visitor cookie is recorded exactly as before, including demo clicks and the authenticated/anonymous flags
- [x] #3 Live: with the poller still running, the visitor row count on production stops growing every 2 s
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Merged #327. Live: with the 2 s WebSocket poller still running, production SiteVisitor count stayed 372,632 over 60 s (read-only). Poller = cookieless ws://127.0.0.1:8000/ from the main Chrome profile; extension not identified. DB later moved to a new Frankfurt Neon project.
<!-- SECTION:NOTES:END -->
