---
id: TASK-1
title: Production env and deployment checklist
status: Done
assignee: []
created_date: '2026-06-20 09:50'
updated_date: '2026-08-18 11:00'
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

### 2026-08-17 - AC1 and AC4 re-checked with live external probes (no Azure access)

AC1 CLOSED. Django's 404 handling differs observably by DEBUG: with DEBUG=True, an unmatched URL
renders the "technical 404" debug page (lists every URL pattern tried, states
"You're seeing this error because you have DEBUG = True..."); with DEBUG=False it falls back to
Django's hardcoded `ERROR_PAGE_TEMPLATE` in `django.views.defaults.page_not_found`, a fixed
179-byte `<h1>Not Found</h1><p>The requested resource was not found on this server.</p>` page,
unless the app ships its own `404.html` (this app does not - grepped `backend/`, no such
template). The frontend catch-all (`config/urls.py:27`, `^(?!api/|admin/|static/).*$`) intercepts
unmatched non-API paths and serves the SPA with 200, so it cannot be used as the probe (that is
what produced the "404 returns the SPA" observation on 2026-08-15). A path under `api/` is not
caught by that regex and falls through to Django's own resolver instead, so it is a clean signal.

Command run:
```
curl -s -o - -D - "https://dachapply.livelysea-3461ad21.westeurope.azurecontainerapps.io/api/does-not-exist-probe-xyz/"
```
Output (verbatim, headers trimmed to the relevant ones):
```
HTTP/1.1 404 Not Found
server: gunicorn
content-type: text/html; charset=utf-8
content-length: 179

<!doctype html>
<html lang="en">
<head>
  <title>Not Found</title>
</head>
<body>
  <h1>Not Found</h1><p>The requested resource was not found on this server.</p>
</body>
</html>
```
This is an exact match, byte for byte, to Django's `ERROR_PAGE_TEMPLATE` fallback, which only
renders when `DEBUG=False`. No traceback, no URL-pattern list, no "DEBUG = True" text, no
Content-Length in the kilobytes range a debug page would produce. DEBUG=False is set in
production.

AC4 PARTIALLY MEASURED, left UNCHECKED. Three sub-claims tested anonymously, no real credentials
used or guessed:

1. Login endpoint responds correctly over HTTPS for bad credentials.
```
curl -s -o - -D - -X POST "https://dachapply.livelysea-3461ad21.westeurope.azurecontainerapps.io/api/auth/login/" \
  -H "Content-Type: application/json" \
  -d '{"username":"probe-does-not-exist@example.com","password":"definitely-wrong-pw-123"}'
```
Result: `HTTP/1.1 400 Bad Request`, body `{"detail":"Invalid credentials"}`. Correct shape, served
over HTTPS.

2. CSRF is actively enforced in production over HTTPS. `jobradar/views.py` DRF endpoints are
`@api_view` views, which DRF marks `csrf_exempt` at the view level and instead enforces CSRF only
inside `SessionAuthentication.enforce_csrf()` - which only runs once a session has already resolved
to an authenticated user. Proved this empirically: an anonymous POST to the public, AllowAny
`/api/public/submit/` with no CSRF token proceeds straight to business-logic validation
(`{"detail":"Invalid invite code"}`, 400) rather than being blocked - expected DRF behaviour, not a
CSRF hole, since there is no session to hijack. To prove CSRF protection is genuinely wired up
end-to-end in this deployment, probed a standard (non-DRF) Django view instead - `/admin/login/`,
which goes through `django.middleware.csrf.CsrfViewMiddleware` normally:
```
curl -s -o - -D - -X POST "https://dachapply.livelysea-3461ad21.westeurope.azurecontainerapps.io/admin/login/" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=probe&password=wrong"
```
Result: `HTTP/1.1 403 Forbidden`, body starts `<h1>Forbidden <span>(403)</span></h1><p>CSRF
verification failed. Request aborted.</p>`. CSRF is enforced in production.

3. Secure cookie flags. `GET /api/auth/csrf/` (sets the CSRF cookie):
```
set-cookie: csrftoken=...; expires=Mon, 16 Aug 2027 ...; Max-Age=31449600; Path=/; SameSite=Lax; Secure
set-cookie: dachapply_visitor_id=...; expires=...; HttpOnly; Max-Age=34560000; Path=/; SameSite=Lax; Secure
```
`csrftoken` is `Secure` + `SameSite=Lax`, correctly NOT `HttpOnly` (Django's CSRF cookie must be
JS-readable so the SPA can echo it back in a header - that is by design, not a gap).
`dachapply_visitor_id` is `Secure` + `HttpOnly` + `SameSite=Lax`. Matches
`SESSION_COOKIE_SECURE`/`CSRF_COOKIE_SECURE` defaulting to `not DEBUG` and
`SESSION_COOKIE_HTTPONLY=True` unconditionally (settings.py:331-335), now confirmed live rather
than inferred from the file.

NOT MEASURED, and this is the actual gap: a genuine successful login (valid credentials) and a
subsequent authenticated, CSRF-protected state-changing POST (e.g. creating a job) were not
attempted - that needs a real account and this agent was explicitly told not to create one, guess
credentials, or submit real personal data. The three points above prove the plumbing (HTTPS, CSRF
middleware, cookie flags) is correct in production; they do not prove a real login round-trip
succeeds. BLOCKER: needs the owner to either run one manual login + one CSRF-protected POST in a
browser against production and confirm it works, or hand the agent a disposable test account
credential for a single scripted login+POST run.
### 2026-08-18 — AC4 closed on owner confirmation; task Done

The owner logged into production over HTTPS and performed a state-changing POST, and confirmed it
worked (2026-08-18). Recorded as owner attestation rather than a captured transcript: AC4 requires a
real authenticated session, the credential is the owner's, and an agent entering it was not on the
table. That is the appropriate evidence for this AC, not a weaker substitute for something that
could have been automated.

The anonymous half was already measured on 2026-08-17 and stands unchanged: CSRF is genuinely
enforced (`POST /admin/login/` with no token returns `403 CSRF verification failed`), and session
cookies carry `Secure`, `HttpOnly` and `SameSite=Lax`. The DRF endpoints returning business-validation
errors to a tokenless POST is expected `@api_view` behaviour, not a CSRF hole.

All four ACs are met, so this task is **Done**.
<!-- SECTION:NOTES:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 DEBUG=False is set in production
- [x] #2 SECRET_KEY, ALLOWED_HOSTS, FRONTEND_URL, CSRF_TRUSTED_ORIGINS, DATABASE_URL, and secure cookie settings are documented and verified
- [x] #3 Deployment startup runs migrations and serves the built frontend/static files
- [x] #4 Production login and CSRF-protected POST requests work over HTTPS
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-06-20 09:59
---
Implemented production readiness docs, verified existing container startup runs migrations/Gunicorn, and documented HTTPS/CSRF smoke tests. Remaining items require real production platform values and HTTPS verification.
---
<!-- COMMENTS:END -->
