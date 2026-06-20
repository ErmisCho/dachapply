---
id: TASK-1
title: Production env and deployment checklist
status: To Do
assignee: []
created_date: '2026-06-20 09:50'
updated_date: '2026-06-20 09:59'
labels:
  - P0
  - deployment
  - security
  - phase-1
milestone: m-1
dependencies: []
priority: high
ordinal: 1000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Make the deployed app safe to run for beta users with the real Neon/Postgres database and HTTPS-only settings.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 DEBUG=False is set in production
- [x] #2 SECRET_KEY, ALLOWED_HOSTS, FRONTEND_URL, CSRF_TRUSTED_ORIGINS, DATABASE_URL, and secure cookie settings are documented and verified
- [x] #3 Deployment startup runs migrations and serves the built frontend/static files
- [ ] #4 Production login and CSRF-protected POST requests work over HTTPS
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-06-20 09:59
---
Implemented production readiness docs, verified existing container startup runs migrations/Gunicorn, and documented HTTPS/CSRF smoke tests. Remaining items require real production platform values and HTTPS verification.
---
<!-- COMMENTS:END -->
