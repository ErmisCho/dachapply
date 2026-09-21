# DACHApply production readiness

Use this checklist before inviting beta users to a deployed instance.

## 1. Required environment

Set these variables in the hosting platform; do not commit real values:

```text
DEBUG=False
SECRET_KEY=<strong unique secret>
ALLOWED_HOSTS=<production hostname>
FRONTEND_URL=https://<production hostname>
CSRF_TRUSTED_ORIGINS=https://<production hostname>
CORS_ALLOWED_ORIGINS=https://<production hostname>
DATABASE_URL=postgresql://...
DB_SSL_REQUIRE=True
DEFAULT_FROM_EMAIL=DACHApply <noreply@your-domain.example>
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=<smtp host>
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=<smtp user>
EMAIL_HOST_PASSWORD=<smtp password>
EMAIL_TIMEOUT=10
SECURE_SSL_REDIRECT=True
USE_X_FORWARDED_PROTO=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
```

Keep `SECURE_HSTS_SECONDS=0` until HTTPS and redirects are confirmed. Then enable HSTS deliberately.

## 2. Build and startup

The production container already builds the React app, collects static files, runs migrations, and starts Gunicorn via `scripts/start-container.sh`.

Manual production-style build:

```bash
cd frontend
npm ci
npm run build
cd ../backend
python manage.py migrate --noinput
python manage.py createcachetable
python manage.py collectstatic --noinput
gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000}
```

## 3. Optional owner-only Codex CV generation

Keep this local-only feature disabled on deployed instances:

```text
CODEX_CV_ENABLED=False
```

Local development defaults it on when `DEBUG=True`; `.env.local.example` also records the explicit owner and `C:\latex` workspace settings. Do not commit CV templates or Codex authentication.

`UserProfile.can_generate_cv` can be granted to any account from Django admin, but generation always uses the site owner's private LaTeX templates and the owner's own photograph, writing into a shared output directory -- there is no per-user template or photo. The admin field's `help_text` says this at the point of granting; do not flip the flag for a second account without the underlying sharing (TASK-99) fixed first.

## 4. Smoke tests after deployment

Run these checks on the deployed HTTPS origin:

- `GET /api/health/` returns HTTP 200 and `{ "status": "ok", "database": "ok" }`.
- Login works.
- CSRF-protected POSTs work, e.g. create/edit a test job.
- Password reset request sends email and the reset link works.
- Static assets load from the built frontend.
- Export and import work for a non-critical test user.

## 5. Recovery: the site is unreachable and Azure refuses writes

Worked example: the 2026-09-16 outage (TASK-239), unreachable for four days. The whole subscription
went read-only because an invoice was past due, and while it stayed in that state the container app
read back as an empty shell.

**The shell was the suspended view, not deletion.** Settling the invoice restored the app's template,
ingress, registries and every secret on it, including the Brevo SMTP credentials, on the same
resource (`systemData.createdAt` never changed). Do not start rebuilding from scratch, and do not
re-enter credentials, before re-reading the resource after the subscription reads `Enabled`.

**Recognising this failure rather than an application bug.** All four together, and no one of them
on its own:

- DNS still resolves `dachapply.livelysea-3461ad21.westeurope.azurecontainerapps.io` to the
  environment's static IP, but TCP never completes — `curl` reports `connect=0.000000s` and times
  out. Reproduce it from somewhere other than your own machine (the uptime-monitor workflow) before
  believing it, or you are debugging your own network.
- Any Azure write fails with `ReadOnlyDisabledSubscription`, including the deploy job.
- `az containerapp show` reports `provisioningState: Failed` with `properties.template.containers`,
  `template.scale`, `configuration.ingress`, `.registries` and `.secrets` all `null`, and no
  revision. Every other container app in the subscription is `Failed` too — an application fault
  does not do that to its neighbours.
- The subscription reads `Warned`, Azure's past-due state:

```bash
az rest --method get \
  --url "https://management.azure.com/subscriptions/f0d59028-5822-491c-8ab1-693dfd9c0057?api-version=2022-12-01" \
  --query state
```

`az account list --all` answers this from the CLI's cached profile and can be hours stale; the
`az rest` call above reads ARM. `Enabled` means the billing problem is over; `Warned` or `Disabled`
means step 1 below has not happened yet, and nothing after it can work.

**Step 1 is a human step and no workflow can perform it.** Settle the outstanding invoice or fix
the payment method in the Azure portal (Cost Management + Billing), signed in as the subscription
owner. There is no API for paying a bill, no credential that can be added to this repository to
make it automatic, and every command below fails with `ReadOnlyDisabledSubscription` until it is
done. Re-run the `az rest` query until it answers `Enabled`.

**Step 2: a reactivated subscription still does not serve. Deploy to wake the compute.** This is
the part that looks like a second, unrelated fault and is not. After `Enabled`, the app can report
`provisioningState: Succeeded` and `runningStatus: Running` with its original FQDN, while the site
answers **HTTP 404 with Azure's own "Azure Container App - Unavailable" page** — there is no compute
behind the ingress yet. The tell is on any revision query:

```
ERROR: (ManagedClusterSuspended) The compute resource for managed enviroment dachapply-env
has been suspended due to subscription has been disabled.
```

(Azure's own message, typo included, and it keeps saying "disabled" after the subscription is not.)
Run the deploy — `gh workflow run "Test, build and deploy" --ref main`, or any push to `main`. It
forces the environment to re-provision and ships the current build in the same pass. On 2026-09-20
that single dispatch took the site from 404 to `{"status":"ok","database":"ok"}` on the original
hostname, with no portal work at all.

The hostname survives a rebuild because it is derived, not allocated: `<app name>` +
`<managed environment defaultDomain>`. As long as the app is called `dachapply` and lives in
`dachapply-env`, it comes back on the same URL that DNS already points at. The managed environment
is the piece that must survive — check it first:

```bash
az containerapp env show -n dachapply-env -g rg-dachapply --query "{state:properties.provisioningState,domain:properties.defaultDomain,ip:properties.staticIp}"
```

**Step 3: verify, then believe it.** The deploy's own check polls `/api/health/` and fails the job
unless it reports `"database": "ok"`, so a green deploy job already means the container started,
migrated and reached Neon. Still run the section 4 smoke tests against the live origin: a health
endpoint is not a rendered board.

**Secrets and variables the deploy needs.** Today's deploy reads only the first two: every other
value below lives on the Azure resource itself, which is exactly the fragility TASK-239 exists to
remove. The rest of this table describes the spec-driven deploy on branch `task-239-azure-outage`,
which fails immediately and names a missing value rather than shipping a container that cannot boot.
It is not merged yet — see that task for what still gates it.

| Name | Kind | Without it |
| --- | --- | --- |
| `AZURE_CREDENTIALS` | secret | no login, nothing deploys |
| `GHCR_PULL_TOKEN` | secret | the app cannot pull its own image |
| `SECRET_KEY` | secret | container refuses to start |
| `DATABASE_URL` | secret | container refuses to start |
| `BREVO_EMAIL_HOST_USER` | secret | starts, and all outbound mail fails at SMTP AUTH |
| `BREVO_EMAIL_HOST_PASSWORD` | secret | starts, and all outbound mail fails at SMTP AUTH |
| `BREVO_DEFAULT_FROM_EMAIL` | variable | container refuses to start |
| `ERROR_ALERT_EMAILS` | variable | error alerting stays off (inert by design) |

The Brevo SMTP pair and the from-address existed **only as environment variables on the Azure
resource**, with the SMTP key in plaintext where `az containerapp show` prints it in full to anyone
holding Reader. The 2026-09-16 outage did not lose them, but nothing in this repository could have
put them back if it had. Set them in GitHub once — and rotate the Brevo key while you are there,
since it has been printed. No password-reset mail, no email verification and no error alerts without
them, and none of those failures are visible from the front page:

```bash
az containerapp show -n dachapply -g rg-dachapply --query "properties.template.containers[0].env"
gh secret set BREVO_EMAIL_HOST_USER
gh secret set BREVO_EMAIL_HOST_PASSWORD
gh variable set BREVO_DEFAULT_FROM_EMAIL --body "DACHApply <verified-sender@example.com>"
```

## 6. Security checks

- Confirm `DEBUG=False` in production.
- Confirm only exact production hostnames are in `ALLOWED_HOSTS` and CSRF/CORS origins.
- Confirm `.env` and secrets are not committed.
- Confirm admin account uses a strong unique password.
- Confirm rate limits remain enabled for login, registration, password reset, public submit, and import endpoints.
- Confirm password reset failures are logged generically and do not expose SMTP credentials or reset tokens.
