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
python manage.py collectstatic --noinput
gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000}
```

## 3. Optional owner-only Codex CV generation

Keep this local-only feature disabled on deployed instances:

```text
CODEX_CV_ENABLED=False
```

Local development defaults it on when `DEBUG=True`; `.env.local.example` also records the explicit owner and `C:\latex` workspace settings. Do not commit CV templates or Codex authentication.

## 4. Smoke tests after deployment

Run these checks on the deployed HTTPS origin:

- `GET /api/health/` returns HTTP 200 and `{ "status": "ok", "database": "ok" }`.
- Login works.
- CSRF-protected POSTs work, e.g. create/edit a test job.
- Password reset request sends email and the reset link works.
- Static assets load from the built frontend.
- Export and import work for a non-critical test user.

## 5. Security checks

- Confirm `DEBUG=False` in production.
- Confirm only exact production hostnames are in `ALLOWED_HOSTS` and CSRF/CORS origins.
- Confirm `.env` and secrets are not committed.
- Confirm admin account uses a strong unique password.
- Confirm rate limits remain enabled for login, registration, password reset, public submit, and import endpoints.
- Confirm password reset failures are logged generically and do not expose SMTP credentials or reset tokens.
