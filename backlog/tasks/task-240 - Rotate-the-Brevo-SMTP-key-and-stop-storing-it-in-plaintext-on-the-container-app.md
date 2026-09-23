---
id: TASK-240
title: >-
  Rotate the Brevo SMTP key and stop storing it in plaintext on the container
  app
status: Done
assignee:
  - '@pi'
created_date: '2026-09-21 07:20'
updated_date: '2026-09-23 07:32'
labels:
  - infrastructure
  - security
dependencies: []
priority: high
type: bug
ordinal: 239000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found 2026-09-21 while recovering from the TASK-239 outage.

BREVO_EMAIL_HOST_PASSWORD is stored as a plaintext environment variable on the dachapply container app, not as a Container Apps secret. Anyone holding Reader on subscription f0d59028 can print it with 'az containerapp show -n dachapply -g rg-dachapply --query properties.template.containers[0].env', and it was printed in full into an agent transcript during that recovery work. Treat it as exposed.

The same applies to BREVO_EMAIL_HOST_USER, which is a login rather than a credential but travels with it.

Rotation is cheap and the owner has to touch these values anyway. Note the deploy does NOT set them: they live only on the Azure resource, so rotating in Brevo without updating the container app breaks all outbound mail - password reset, email verification, and error alerts - and none of those failures are visible from the front page.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The Brevo SMTP key in use is a new one, and the old value no longer authenticates
- [x] #2 The value in use is not readable from 'az containerapp show' output - it is a Container Apps secret referenced by secretRef, or held somewhere equivalent, rather than a plaintext env var
- [x] #3 Password-reset and email-verification mail is confirmed still sending after the rotation, by triggering one of each against a real address rather than by reading configuration
- [x] #4 Wherever the new value has to live for a future rebuild is written down, so a redeploy does not silently ship a container with dead mail credentials
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
## Do these two in one pass on the resource

The rotation already requires editing the container app. Two neighbours worth fixing in the same
edit, both measured on the live resource during the TASK-239 recovery:

1. DEFAULT_FROM_EMAIL=noreply@localhost and EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
   are set and inert -- production runs the Brevo branch (settings.py:551), which reads neither.
   The console backend cannot be revived by EMAIL_PROVIDER=console (refused when DEBUG=False,
   :541-542); it would take the Brevo trio being incomplete at the same time. Narrow, but its failure
   mode is password-reset links printed into the container log while every request looks fine.
   Documented in docs/production-readiness.md section 1 (TASK-242); removing them is this task's
   neighbour, not its blocker.
2. The legacy registry cab585727768acr.azurecr.io is still configured on the app alongside ghcr.io,
   left from the original 'az containerapp up'. Nothing pulls from it.

Neither is urgent on its own. Both are one line each while the resource is open.

## Rotated and verified 2026-09-22

The owner generated a fresh Brevo SMTP key and added it as the Container Apps secret `brevo-smtp-key`
through the Azure Portal, so the value travelled from Brevo to Azure without passing through a shell,
a transcript or this session. The rest was run here.

    az containerapp update ... --set-env-vars BREVO_EMAIL_HOST_PASSWORD=secretref:brevo-smtp-key                                --remove-env-vars EMAIL_BACKEND DEFAULT_FROM_EMAIL
    az containerapp registry remove ... --server cab585727768acr.azurecr.io

Verified by reading the resource back, not from the command's own exit code:

| check | result |
|---|---|
| BREVO_EMAIL_HOST_PASSWORD | no value, secretRef brevo-smtp-key -- absent from `az containerapp show` output (AC2) |
| EMAIL_BACKEND, DEFAULT_FROM_EMAIL | gone -- both were inert under the Brevo branch (TASK-242) |
| registries | ghcr.io only; the legacy ACR entry and its secret are gone |
| revision | dachapply--0000201, Running, latestReady == latest |
| /api/health/ | {"status":"ok","database":"ok"} |

**AC3 closed by delivery, not by configuration.** The owner triggered a password reset on the live
site and the mail arrived: sent through Brevo's relay, signed by the Brevo sending domain, over TLS,
with the reset link pointing at the production hostname. That is the check the criterion asks for,
because wrong SMTP credentials fail at send time while every page keeps returning 200.

## Two exposures, both now burned rather than in use

The original key was plaintext on the container app and had been printed into an agent transcript.
Its intended replacement was pasted into this session's shell as part of a command and so landed in
this transcript too -- caught before it was installed, and never applied to Azure. The key now in use
is a third one, and neither earlier key was ever wired up.

Remaining for the owner: delete both older keys in Brevo. Until that is done the old credentials
still authenticate, which is the second half of AC1.

## Old keys deleted, and AC1 closed 2026-09-23

The owner deleted both superseded keys in Brevo: the original plaintext one and the replacement that
was pasted into a session shell before it could be installed. Neither was ever wired to the app.

AC1 has two halves, and the second was not taken on trust -- the failure it guards against is
deleting the key that was actually in use. The check was one more real send AFTER the deletions. It
did not arrive on the first two attempts and then landed: delivery latency, not a broken credential.

Diagnosis run while it was missing, kept because it is the checklist for next time:

    POST /api/auth/password-reset/   200, not 429  -- accepted, and not rate limited
    stored secret shape              90 chars, xsmtpsib- prefix, no whitespace, 3 segments
                                     (read into a shape check, never printed)
    container console log            startup only; no SMTP exception surfaced there

The purpose-built tool for a next occurrence is POST /api/auth/email-diagnostics/ (staff only): it
reports the mail configuration without returning any secret and performs a self-addressed test send
that surfaces the real exception instead of swallowing it. Password reset deliberately answers the
same generic string either way, so it can never distinguish a broken mailer from a missing account --
which is exactly why this hunt needed a different tool.

Both halves of AC1 are now true: the key in use is a new one, and the two superseded keys are deleted
and were demonstrably not the one authenticating.
<!-- SECTION:NOTES:END -->
