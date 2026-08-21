---
id: TASK-160
title: Tell the owner when the mailbox check stops working
status: Done
assignee: []
labels:
  - backend
  - ops
  - mailbox
dependencies:
  - TASK-88
  - TASK-116
priority: high
ordinal: 160000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner question, 2026-08-21: "when this happens I get an email with a specific link to renew it?"
Measured answer: **no**. Nothing tells the owner when the mailbox check stops working. It stops, and
they find out by visiting the Mailbox page and noticing a run that says `Failed: ...`.

Why the existing alerting does not cover it, measured rather than assumed:

    local DEBUG:            True          -> require_debug_false blocks the mail_admins handler
    local ADMINS:           []            -> no recipient configured locally anyway
    local EMAIL_BACKEND:    console       -> the machine cannot send mail at all
    local EMAIL_HOST_USER:  (unset)       -> no SMTP credentials

TASK-88's alerting works, and it works on the DEPLOYED site — which is not where the mailbox check
runs. The check runs on the owner's own machine, precisely because that is where the Gmail
credentials live. So the one component that can send email is the one that never sees the failure.

Two failure modes need covering, and the second is the one that is genuinely silent:

1. **The token stopped working.** In "Testing" publishing status Google expires the refresh token
   after about 7 days; it can also be revoked, or invalidated by a password change. `run_check`
   records the error on the `MailboxRun` and the Mailbox page renders `Failed: ...` — visible, but
   only to someone already looking.
2. **No check ran at all.** The laptop was off, asleep, or the scheduler stopped. There is no failed
   run to look at — there is simply nothing, which looks identical to "no new mail" from the UI.

The deployed site can see both, because it reads the same database as the local check writes to.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The deployed site can determine mailbox health from the shared database alone: the latest run's error, and how long it has been since the last SUCCESSFUL run — no dependency on anything the owner's machine does at alert time
- [x] #2 An email reaches the owner when the check is failing OR has not succeeded within a configurable window (default 24 hours), sent through the deployed site's working mail path, not through the logging handler that `require_debug_false` disables locally
- [x] #3 The email says what to actually do: the exact `manage.py gmail_oauth_setup` re-authorization command, and that publishing the OAuth consent screen removes the 7-day expiry entirely
- [x] #4 It does not nag: at most one alert per cooldown window (reuse the existing ERROR_ALERT_COOLDOWN idea rather than inventing a second mechanism), and a recovered check alerts again only after it next breaks — not on every probe in between
- [x] #5 Triggered by the existing uptime-monitor workflow rather than new infrastructure, and a failure to alert never fails that workflow's uptime verdict — a broken mailbox is not the site being down
- [x] #6 The endpoint is safe to expose unauthenticated: it reveals nothing about the mailbox beyond a coarse status, cannot be used to flood the owner with mail (the cooldown bounds it), and returns 200 whether healthy or not so the workflow's `--fail` still means "the site is down"
- [x] #7 Verified end to end against the real deployment: with a genuinely stale/failing state, the email arrives and names the right remedy; with a healthy state, no email is sent
- [x] #8 Backend tests cover healthy, failing, stale, and cooldown-suppressed cases; no test sends real mail or contacts a real mailbox
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-08-21 close-out. Shipped in PR #67 (merge ece3584), deployed, and verified END TO END against
the real deployment with the owner's approval to create and remove a temporary row:

    healthy state          GET /api/mailbox-health/ -> 200 {"status":"ok"}, no email
    failing state          -> 200 {"status":"failing"}, ONE email delivered to the owner
    second probe, same     -> 200 {"status":"failing"}, NO second email (cooldown held)
    after cleanup          -> 200 {"status":"ok"}

The owner confirmed the delivered email names the remedy (the gmail_oauth_setup command). The
verification row (MailboxRun id 14, error text carrying an explicit "TASK-160 AC7 verification row"
marker) was deleted immediately afterwards: 13 runs before, 13 runs after, latest run error back to
''.

Why this task existed at all, worth keeping: TASK-88's alerting is real and works, and it is blind to
this failure by construction. The check runs where the credentials are - the owner's machine - and
that machine has DEBUG=True (so require_debug_false disables mail_admins), ADMINS empty, and the
console email backend with no SMTP credentials. The component that can send mail is the one that
never sees the failure. Reading either half alone would have concluded "we have alerting".

Related outcome recorded in docs/email-setup.md in the same PR: publishing the OAuth consent screen
to escape the 7-day testing-mode expiry is NOT available to this app - the Publish button is greyed
out pending a home page, privacy policy and a Search Console-verified authorised domain, and
*.azurecontainerapps.io cannot satisfy that. So the 7-day re-authorization stands, and this watchdog
is what makes that acceptable: it is noticed for you rather than discovered days later.

The staleness threshold should not be hardcoded to 24 hours without thought: the owner's configured
cadence is `UserProfile.mailbox_check_cadence_minutes`, and quiet hours plus a closed check window
mean legitimate gaps. A fixed generous default (24h) with a setting to override is the honest
starting point; deriving it from cadence is a refinement, not a requirement.

Do not put this behind a new shared secret unless AC6 cannot otherwise be met — every new secret is
one more thing to set in two places and one more thing to leak (see TASK-157). A public endpoint
whose only side effect is a cooldown-bounded email to a fixed, configured address is the smaller
surface.

`/api/health/` must keep meaning "is the site up" for the uptime workflow's `--fail` logic. Do not
overload it.
<!-- SECTION:NOTES:END -->
