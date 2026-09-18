---
id: TASK-239
title: >-
  Rebuild the production container app from the repository after the Azure
  outage
status: To Do
assignee: []
created_date: '2026-09-18 10:23'
updated_date: '2026-09-18 10:24'
labels:
  - infrastructure
  - backend
dependencies: []
priority: high
type: bug
ordinal: 238000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Measured 2026-09-18, after the owner reported the site unreachable.

Production has been down since 2026-09-16T04:03Z (last successful uptime-monitor run; every run since has failed). DNS still resolves dachapply.livelysea-3461ad21.westeurope.azurecontainerapps.io to 20.23.217.200, but TCP connect never completes - curl reports connect=0.000000s and times out at 21s from this machine, and the GitHub-hosted uptime monitor times out identically, so it is not a local network problem.

Root cause, read from Azure rather than guessed: subscription f0d59028-5822-491c-8ab1-693dfd9c0057 (tenant ermis702gmail.onmicrosoft.com) is in state **Warned** - Azure's past-due state - with quotaId PayAsYouGo and spendingLimit Off, so this is an unpaid invoice or a failed payment method, not an exhausted free credit. Writes to the subscription are refused: the deploy job for PR #157 failed with ReadOnlyDisabledSubscription. Both container apps in that subscription (dachapply and the unrelated sms-spam-demo-app) are provisioningState Failed, which is a whole-subscription event rather than an application fault.

**What Azure took with it.** The container app object still exists but is an empty shell: template.containers, scale, configuration.ingress, configuration.registries and configuration.secrets are all null, and there is no revision. The managed environment dachapply-env survived (Succeeded), and the app keeps its customDomainVerificationId, so recreating the app with the same name in the same environment should return the same FQDN.

**Why paying the bill is not enough on its own.** .github/workflows/deploy-container-apps.yml does az containerapp registry set + az containerapp update and then asserts the ingress FQDN is non-empty. Against an app with a null template that cannot succeed. Worse, --set-env-vars is additive by design, and every other production variable - DATABASE_URL, SECRET_KEY, the mail credentials - lived only on the Azure resource and is now gone, so even a successful update would start a container that raises ImproperlyConfigured. The production database itself is untouched: it is Neon, outside Azure, and the local runtime reports {"status":"ok","database":"ok"} against it.

This task is blocked until the subscription is writable again; that step belongs to the owner and cannot be automated from here.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The deploy workflow brings the site back when the container app is missing or in a Failed state with no template, proven by a real deploy run followed by the live health endpoint returning {"status":"ok","database":"ok"} - not by reading the YAML
- [ ] #2 Every setting the container needs to start is declared in the repository (ingress, target port 8000, min replicas, registry, and each variable listed in docs/production-readiness.md), with secret values injected from GitHub secrets and no real value committed
- [ ] #3 The restored site answers on the same hostname as before, or the task records the new hostname and every place in the repo, DNS and docs that has to change with it
- [ ] #4 A deploy against a healthy app still updates in place - verified by a second consecutive run that keeps the same FQDN and does not recreate the app
- [ ] #5 The human step that no workflow can perform - settling the Azure subscription when it is past due - is written into the runbook next to the recovery command
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
0. BLOCKER, owner only: the subscription must leave the Warned state. Azure portal as ermis702@gmail.com -> Cost Management + Billing -> settle the outstanding invoice or fix the payment method. No change in this repository can do this, and every step below fails with ReadOnlyDisabledSubscription until it is done.
1. Re-read the subscription state before touching anything: az rest --method get --url https://management.azure.com/subscriptions/f0d59028-5822-491c-8ab1-693dfd9c0057?api-version=2022-12-01 must report state Enabled.
2. Recreate the app rather than update it. Measured 2026-09-18: the environment dachapply-env is Succeeded, its defaultDomain is livelysea-3461ad21.westeurope.azurecontainerapps.io and its staticIp is 20.23.217.200 -- the address DNS already resolves to -- so an app named dachapply created in that environment returns the same URL. The Failed shell may have to be deleted first; check whether create --yaml can overwrite it before deleting anything.
3. Recover the environment values. They existed only on the Azure resource and are gone: DEBUG, SECRET_KEY, ALLOWED_HOSTS, FRONTEND_URL, CSRF_TRUSTED_ORIGINS, CORS_ALLOWED_ORIGINS, DATABASE_URL, DB_SSL_REQUIRE, the EMAIL_* block, and the SECURE_*/cookie flags (docs/production-readiness.md section 1). DATABASE_URL points at Neon, which is untouched and can be re-read from the Neon dashboard. A new SECRET_KEY is acceptable -- it only invalidates existing sessions, so users log in again.
4. Put the whole definition in the repository as a containerapp YAML spec the workflow applies, with every secret injected from GitHub secrets at apply time and no real value committed. That is what turns this outage from a hand-rebuild into a workflow run.
5. Make the deploy job create-or-update rather than update-only, and keep the update path in place for the healthy case (AC4 wants a second consecutive run that neither recreates the app nor changes the FQDN).
6. Verify against the live site: /api/health/ answering {status: ok, database: ok} on the original hostname, and the board rendering rather than a 200 alone. Then, and only then, close TASK-237 and TASK-238, whose production verification is blocked by this same outage.
7. Write the runbook entry, including step 0, next to the recovery command -- the next person hitting this needs the billing step in the same place as the az commands.
<!-- SECTION:PLAN:END -->
