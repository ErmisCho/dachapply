---
id: TASK-88
title: Add production error logging and alerting
status: In Progress
assignee:
  - '@claude'
created_date: '2026-08-16 00:43'
updated_date: '2026-08-16 15:05'
labels:
  - ops
  - backend
dependencies: []
priority: medium
ordinal: 93000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
No LOGGING config and no error tracker exist anywhere in backend/config (grep: no matches), so production 500s live only in Container Apps stdout until someone goes looking. The uptime monitor from TASK-3 (.github/workflows/uptime-monitor.yml, every 30 min) catches "down" — it cannot catch "erroring": a broken import path or a failing CV endpoint returns errors to users for days while /health stays green.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Unhandled 500s produce a durable, pushed signal — Django LOGGING to mail_admins/webhook, or a Sentry DSN via env var
- [ ] #2 A deliberately raised test error reaches the channel end to end in production, recorded in the closing notes
- [x] #3 Noise-guarded: 404s and throttled (429) requests do not alert
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Sentry's free tier is the lazy complete answer (grouping, rate-limiting, context for free); if avoiding the dependency, a LOGGING dict with an ERROR-level handler posting to a webhook is ~20 lines. Either way it is configuration, not code.

### Progress (2026-08-16) — prep landed in Wave 6, AC1/AC2 need the owner

**The task's premise was wrong, and the correction makes it more valuable, not less.** It assumed
production 500s "live only in Container Apps stdout until someone goes looking". Measured against the
committed settings: there was no `LOGGING` config at all, so with `DEBUG=False` Django's default
sends `django.request` errors to `mail_admins` (filtered by `require_debug_false`) and nowhere else —
and with `ADMINS` empty that is nothing. Gunicorn runs without `--access-logfile`, so not even a
status line survived. A/B on the same 500:

    before   nothing. no stdout, no stderr, no mail.
    after    [..] ERROR django.request Internal Server Error: /api/... + full traceback on stderr

So even with no recipient configured, this wave turned invisible 500s into visible ones.

Chose a `LOGGING` dict over Sentry, and the reasoning is worth keeping: Sentry buys grouping, search,
retention and rate limiting, at the cost of a monkeypatching SDK, a third-party account, a DSN
secret and a second delivery path — to push a signal over a channel this repo already has working
(the password-reset mail proven in TASK-2). Of the four things given up, only **rate limiting has a
failure mode if absent**: a crash loop on a hot path emails once per request and burns the SMTP
quota that password reset depends on, i.e. alerting that breaks the thing it watches. That one is
replaced by a 15-line filter keyed on the innermost traceback frame, so distinct bugs still alert
separately. It deliberately does not use `DatabaseCache` like the throttles do — the database going
down is the failure most likely to cause the storm, so the cooldown must not depend on it.

**AC3 measured rather than assumed**, which turned up two things the ticket never mentioned:

    GET /api/definitely-not-a-route/   django.request  WARNING  404  -> 0 emails
    login throttled -> 429            django.request  WARNING  429  -> 0 emails
    GET /boom/ (RuntimeError)         django.request  ERROR    500  -> 1 email

DRF's `Throttled` logs nothing of its own; the only record for a 429 comes from Django's
`log_response`, which picks ERROR only for status >= 500. So 4xx is excluded by construction, not by
a rule bolted on. And `DisallowedHost` logs at **ERROR** on `django.security` — under Django's stock
wiring that propagates to a logger carrying `mail_admins`, so merely setting `ADMINS` would have
emailed on every bot probing the container by IP. `django.security` is deliberately console-only,
with a test pinning it.

**Inert until configured, proven by booting it:** production-shaped, `DEBUG=0`, with the three new
variables unset —

    DEBUG: False | ADMINS: []
    django.request   handlers=['AdminEmailHandler']   (no recipients -> sends nothing)
    django.security  handlers=[]                      (bot noise excluded)

and `manage.py check --deploy` raises no new issues. Suite: **216 passed** (207 + 9 new), all
asserting on `mail.outbox` — "would the owner have been told?" — rather than on log records.

The three new variables are documented in `.env.example` (added at close, since `docs/` belonged to
the other agent this wave).

**Owner actions:**
- **AC1** — set one variable on the Container App and alerting is live:
  `ERROR_ALERT_EMAILS=ermis.chorinopoulos@gmail.com`. Optionally `SERVER_EMAIL`, which **must** be a
  Brevo-verified sender or the alert silently bounces.
- **AC2** — after AC1 takes a revision, trigger a deliberate 500 in production, confirm the mail
  arrives with subject prefix `[DACHApply] `, and record it here.
<!-- SECTION:NOTES:END -->
