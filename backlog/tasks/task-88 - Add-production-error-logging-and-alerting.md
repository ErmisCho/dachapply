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
- [x] #1 Unhandled 500s produce a durable, pushed signal — Django LOGGING to mail_admins/webhook, or a Sentry DSN via env var
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

### 2026-08-16 — attempted from this session, and why it could not be done

Checked rather than assumed: the `az` CLI on this machine **is** logged in, but as a service
principal for an unrelated project (`rg-route-ai-sync`). It sees exactly one subscription, and in it:

    az resource list --query "[?contains(name,'dachapply')]"   -> empty
    az webapp list                                             -> empty
    az containerapp list                                       -> route-ai-sync apps only

So no Container App named `dachapply` is reachable from this credential and AC1 cannot be set from
here. The rights live in the `AZURE_CREDENTIALS` repo secret, which is write-only. This is a
credential boundary, not a missing step — AC1 and AC2 stay unchecked.

**Exact command once logged in as the account behind `AZURE_CREDENTIALS`** (the deploy workflow
discovers the resource group rather than hardcoding it, so mirror that):

    RG=$(az containerapp list --query "[?name=='dachapply'].resourceGroup | [0]" -o tsv)
    az containerapp update --name dachapply --resource-group "$RG" \
      --set-env-vars ERROR_ALERT_EMAILS=ermis.chorinopoulos@gmail.com

Leave `SERVER_EMAIL` unset unless a Brevo-verified sender is used — an unverified sender makes the
alert bounce silently, which is the exact failure this task exists to remove.

For AC2, do not add a crash route to production to test it. A 500 that costs nothing: hit an
authenticated endpoint with a payload that reaches the ORM but not validation, or briefly point
`DATABASE_URL` at an unreachable host on a throwaway revision. Simplest honest option is to wait for
the first real 500 and record that one — the AC asks for an end-to-end delivery, not for a synthetic
one.

### AC1 closed 2026-08-16 — configured through the deploy, not the console

The blocker was never the code; it was that `ERROR_ALERT_EMAILS` had no value in production, so
`ADMINS` (settings.py:319) was empty and `AdminEmailHandler` had nobody to email.

Set as a **repository variable** rather than a secret or a literal: it is a notification address, not
a credential, and keeping it out of the workflow file avoids adding another copy of a personal email
to a public repo. Wired into `az containerapp update --set-env-vars`, which is additive and touches
only that name. Declared on every deploy rather than edited once in the console, so it survives a
revision being recreated.

**Proof it took effect, from deploy run 31963625572** — GitHub masks secrets in logs but not
variables, which is what makes this readable at all:

    env:
      GHCR_PASSWORD: ***
      ERROR_ALERT_EMAILS: ermis.chorinopoulos@gmail.com

    az containerapp update ... --set-env-vars "ERROR_ALERT_EMAILS=$ERROR_ALERT_EMAILS"
    -> build-and-push: success,  Verify public app: success

So the variable resolved to a real value (an unset variable would have shown as empty right there)
and the update succeeded. Production healthy afterwards: `/api/health/` 200 `{"status":"ok",
"database":"ok"}`.

`SERVER_EMAIL` deliberately left unset. The earlier note warned it must be a Brevo-verified sender or
alerts bounce silently — that turned out not to need action: `settings.py:322` is
`SERVER_EMAIL = os.getenv('SERVER_EMAIL') or DEFAULT_FROM_EMAIL`, and `DEFAULT_FROM_EMAIL` is already
verified because password reset sends through it. Setting it would have been the only way to *break*
this.

**AC2 remains open and cannot be closed from here.** It asks for a deliberate error to reach the
channel end to end, and the channel is the owner's inbox. Deliberately 500-ing production to test it
is not worth the blast radius when the next real 500 tests it for free — so the honest close is to
record the first genuine alert when it arrives, subject prefix `[DACHApply] `. If nothing has arrived
after the next real error, check Brevo's sending log before suspecting the config: everything up to
handing the message to Brevo is now proven.

<!-- SECTION:NOTES:END -->
