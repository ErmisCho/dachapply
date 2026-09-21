---
id: TASK-240
title: >-
  Rotate the Brevo SMTP key and stop storing it in plaintext on the container
  app
status: To Do
assignee: []
created_date: '2026-09-21 07:20'
updated_date: '2026-09-21 12:24'
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
- [ ] #1 The Brevo SMTP key in use is a new one, and the old value no longer authenticates
- [ ] #2 The value in use is not readable from 'az containerapp show' output - it is a Container Apps secret referenced by secretRef, or held somewhere equivalent, rather than a plaintext env var
- [ ] #3 Password-reset and email-verification mail is confirmed still sending after the rotation, by triggering one of each against a real address rather than by reading configuration
- [ ] #4 Wherever the new value has to live for a future rebuild is written down, so a redeploy does not silently ship a container with dead mail credentials
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
<!-- SECTION:NOTES:END -->
