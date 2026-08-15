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

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Checked against the live app on 2026-08-15, but BOTH ACs are left unchecked because the evidence is
external and indirect. Confirming them takes one command with access to the Container App, which an
agent working from this machine does not have (the local az identity sees a different subscription).

AC1 evidence, strong but not conclusive:
- http:// answers 301 to https. Consistent with SECURE_SSL_REDIRECT, which defaults to `not DEBUG`
  (settings.py:213) - but Container Apps ingress can issue that redirect itself, so it is not proof.
- The live host answers 200. Under DEBUG=True, ALLOWED_HOSTS defaults to localhost,127.0.0.1,
  testserver (settings.py:71), so the real hostname would be rejected with 400 DisallowedHost -
  unless ALLOWED_HOSTS was also set explicitly, which is possible.
- A 404 path returns the SPA, with no Django traceback anywhere in the body.
TO CONFIRM: `az containerapp show -n dachapply -g <rg> --query "properties.template.containers[0].env"`
and check DEBUG is absent or False.

AC2: HTTPS is enforced and the security headers are present (X-Frame-Options: DENY,
X-Content-Type-Options: nosniff, Referrer-Policy: same-origin). Cookie flags are correct by
construction: SESSION_COOKIE_SECURE and CSRF_COOKIE_SECURE both default to `not DEBUG`
(settings.py:208-209), SESSION_COOKIE_HTTPONLY is unconditional, and SECURE_PROXY_SSL_HEADER is set
so Django sees the real scheme behind the ingress. A genuine end-to-end login plus CSRF-protected
POST needs real credentials, so it is not verified here - the owner logs in daily, which is the
practical evidence.

HARDENING GAP: SECURE_HSTS_SECONDS defaults to '0' (settings.py:216), so no Strict-Transport-Security
header is sent - confirmed absent from the live response. The default is deliberately conservative,
since a long HSTS max-age is hard to undo. Enabling it is an env var on the Container App
(SECURE_HSTS_SECONDS=31536000), worth doing once the hostname is final.
<!-- SECTION:NOTES:END -->

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
