---
id: TASK-88
title: Add production error logging and alerting
status: Done
assignee:
  - '@claude'
created_date: '2026-08-16 00:43'
updated_date: '2026-08-17 15:50'
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
- [x] #2 A deliberately raised test error reaches the channel end to end in production, recorded in the closing notes
- [x] #3 Noise-guarded: 404s and throttled (429) requests do not alert
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->

### 2026-08-20 — AC2 closed, end to end in production

With the owner's approval, a deliberate 500 was raised on the DEPLOYED site the way this task's own
notes prescribed ("a 500 that costs nothing"): `POST /api/prompts/generate/` with
`{"job_ids": ["not-a-number"]}`. That reaches the ORM and fails there
(`views.py:1278`, `filter(id__in=ids)` -> `ValueError: Field 'id' expected a number but got
'not-a-number'`), so it writes nothing, changes no code, and adds no crash route. The site stayed
healthy through it: board 200 with 73 jobs, `/health/` 200.

The alert arrived. Delivered to ermis.chorinopoulos@gmail.com at 2026-08-20 21:28 Europe/Vienna,
from `DACHApply <...@11494992.brevosend.com>` with `Reply-To` the owner, subject:

    [DACHApply] ERROR (EXTERNAL IP): Internal Server Error: /api/prompts/generate/

carrying the exception type, value, full traceback and request context. That is AC2's end-to-end
delivery, on the real deployment, for a real error. AC1 and AC3 were already proven.

**The proof immediately surfaced a security defect, filed as TASK-157:** the settings dump in that
email prints `DATABASE_URL` in full - the complete production Neon connection string including its
password - because Django's `SafeExceptionReporterFilter` masks by setting NAME
(`API|TOKEN|KEY|SECRET|PASS|SIGNATURE`) and `DATABASE_URL` matches none of them. `SECRET_KEY`,
`EMAIL_HOST_PASSWORD` and `DATABASES[...]['PASSWORD']` were all correctly masked in the same email.
So alerting works, and every 500 it reports mails the database credentials until TASK-157 lands.

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

### 2026-08-17 — checked whether AC2 is verifiable without the owner's inbox, and it is not

TASK-70 AC3 closed by reading GitHub's own notification API instead of the owner's email. Checked
whether an equivalent exists here: a Brevo API that would show whether the alert was delivered,
without opening the inbox.

**Every Brevo credential this repo ever configures is an SMTP relay login, not the Transactional API.**
Grepped every place Brevo is wired up:

    backend/config/settings.py:276-278   BREVO_EMAIL_HOST_USER / BREVO_EMAIL_HOST_PASSWORD -> EMAIL_HOST_USER/PASSWORD
    .env.example, .env.azure.example,
    .env.local-smtp.example              BREVO_EMAIL_HOST=smtp-relay.brevo.com, BREVO_EMAIL_HOST_USER=..., BREVO_EMAIL_HOST_PASSWORD=...
    grep -r "BREVO_API\|api.brevo.com" .  -> no matches anywhere in the repo

Brevo's sending log lives behind `api.brevo.com/v3/...` and needs a separate Transactional-API key
(`xkeysib-...`, sent as an `api-key` header) — an SMTP login/password does not authenticate against
it. This repo has never had that key as a concept, so there is nothing to look up even in principle,
and `.env` (the local file) has no `BREVO_*` variable at all — checked directly, it holds only Neon/CV
settings, no mail credentials of any kind. Local dev cannot even send through Brevo, let alone query
its log.

**`/api/auth/email-diagnostics/` is a real endpoint but answers a different question.** Read the view
(`backend/jobradar/views.py:335-370`) and its tests
(`backend/jobradar/tests/test_api.py:1250-1289`): GET returns non-secret SMTP config (host, ports,
whether credentials are *set*), and POST calls `send_mail(...)` straight to `request.user.email` using
`DEFAULT_FROM_EMAIL` — that is the password-reset delivery path, proving Brevo SMTP works at all. It
never touches `ADMINS` / `AdminEmailHandler` / `mail_admins`, which is the actual AC2 channel, and it
is staff-only (`if not request.user.is_staff: 404`), so even reachable it would need the owner's own
authenticated production session — not something this session has or should acquire.

**Conclusion: AC2 is not verifiable from this environment by any channel, not just the inbox.** There
is no Brevo credential of the kind (API key) that would show a sending log, and the one diagnostics
endpoint that exists checks a different mail path under a login this session does not have. Per the
hard rule for this task, no error was deliberately raised in production to test it. AC2 stays open.

**Exact blocker, precisely named:** the owner needs to (a) open the inbox at
`ermis.chorinopoulos@gmail.com` and check for a `[DACHApply] ` subject after the next real production
500 — no synthetic trigger, per the notes above — and record what arrived here; or (b), if a
same-day answer is wanted, add a Brevo **Transactional API key** (`BREVO_API_KEY`, not the existing
SMTP login) so `GET https://api.brevo.com/v3/smtp/statistics/events` could be queried instead. (b) is
a new credential this repo has never held, so it is a decision for the owner, not something to add
unilaterally here.

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

### 2026-08-18 — a DACHApply email did arrive, and it does NOT close AC2

Searching the owner's inbox for `DACHApply` returned a delivered message:
`"DACHApply reminders: 6 items need attention"`, 2026-08-18 04:00. It is tempting to read that as
AC2 satisfied. It is not, and the distinction is worth writing down so it is not re-litigated.

That email is the **follow-up digest**, whose subject is built at
`backend/jobradar/services/followup_digest.py:67`. The error alert AC2 asks about is a different
mechanism entirely: Django's `AdminEmailHandler`, fed by `ADMINS` (`settings.py:386`, populated from
`ERROR_ALERT_EMAILS`), fired by an unhandled 500 and carrying the `[DACHApply] ` subject prefix.
Different trigger, different sender, different subject shape.

**What it does prove, and it is not nothing:** the Brevo SMTP path delivers to the owner's inbox and
is not silently bouncing. Since `SERVER_EMAIL` falls back to `DEFAULT_FROM_EMAIL` (`settings.py:322`),
the alert would go out over that same working sender. So every link in the chain except the trigger
is now evidenced.

**AC2 still requires an alert that actually fired.** It closes when a real production 500 delivers a
`[DACHApply] `-prefixed mail — deliberately not manufactured, since 500-ing production to satisfy a
checkbox is a worse trade than waiting. If nothing arrives after the next genuine error, check
Brevo's sending log before suspecting the configuration.
<!-- SECTION:NOTES:END -->
