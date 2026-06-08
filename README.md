# DACHApply

This is a full-stack Django and React application for collaborative job lead collection, structured job evaluation, manual ChatGPT-based analysis, and application prioritization.

## Live app
Hosted on Azure Container Apps: https://dachapply.livelysea-3461ad21.westeurope.azurecontainerapps.io

Access may require an account.

## Purpose
DACHApply is a private job intelligence dashboard for a Software Engineer job search in Austria/Germany. Friends can submit relevant job links using invite codes. The owner reviews leads, generates reusable ChatGPT prompts without paid LLM APIs, imports strict JSON evaluations, and tracks applications, notes, and follow-ups.

## Architecture
- `backend/`: Django, Django REST Framework, SQLite, Django auth/admin, pytest tests
- `frontend/`: React + TypeScript + Tailwind CSS (Vite)
- Production: PostgreSQL via `DATABASE_URL` is supported; SQLite remains suitable only for local/MVP testing
- React production build is served by Django/WhiteNoise

## Core workflow
1. Friend opens `/public-submit`, enters invite code once, and may submit either full job details or just a job URL. After a successful submission, the browser remembers the invite code for next time.
2. Owner logs in at `/login` and views dashboard.
3. Owner can paste a list of job links in `/prompts` and generate a Bulk Links Prompt for ChatGPT. The returned JSON can create new jobs with details and nested evaluations.
4. Owner can also select URL-only/incomplete existing jobs in `/prompts` and generate a Missing Details Prompt for ChatGPT.
5. Owner pastes ChatGPT's `job_updates` or `jobs` JSON into `/import`; the app updates or creates the correct job records.
6. Owner selects completed jobs in `/prompts` and generates an Evaluation Prompt with embedded candidate profile.
7. Owner pastes strict evaluation JSON into `/import`.
8. Backend validates required fields and stores `JobEvaluation` records.
9. Dashboard/job detail pages show score, priority, recommendation, gaps, status, and next action with clear badges.

This reduces repeated LLM token usage by centralizing reusable prompts and structured imports while avoiding paid LLM API calls.

## Backend stack
Django, Django REST Framework, built-in auth/session auth, admin, SQLite, WhiteNoise, pytest.

## Frontend stack
React, TypeScript, React Router, Tailwind CSS, fetch-based API client with session cookies.

## Local setup and run instructions

From the project root:

```bash
python -m venv .venv
# Windows PowerShell: .venv\\Scripts\\Activate.ps1
# Windows cmd: .venv\\Scripts\\activate.bat
# macOS/Linux/Git Bash: source .venv/bin/activate

pip install -r requirements.txt
cd frontend
npm install
cd ../backend
python manage.py migrate
python manage.py createsuperuser
python manage.py seed_demo
python manage.py runserver 127.0.0.1:8000
```

In a second terminal:

```bash
cd frontend
npm run dev
```

Open `http://localhost:5173`.

Useful pages:
- Owner login: `http://localhost:5173/login`
- Dashboard: `http://localhost:5173/`
- Friend submission: `http://localhost:5173/public-submit`
- Prompt generator: `http://localhost:5173/prompts`
- Import evaluation JSON: `http://localhost:5173/import`
- Data export/import: `http://localhost:5173/export`
- Django admin: `http://127.0.0.1:8000/admin/`

Seed invite code:

```text
FRIEND-DEMO
```

For a quick non-interactive local demo user instead of `createsuperuser`, run:

```bash
cd backend
python manage.py shell -c "from django.contrib.auth.models import User; User.objects.filter(username='owner').exists() or User.objects.create_superuser('owner','owner@example.com','ownerpass')"
```

Then log in with `owner` / `ownerpass`.

For same-origin production-style local serving through Django:

```bash
cd frontend
npm install
npm run build
cd ../backend
python manage.py collectstatic --noinput
python manage.py migrate
python manage.py runserver 127.0.0.1:8000
```

Open `http://127.0.0.1:8000`.

## User data export/import
Logged-in users can open `/export` and export jobs/application data, dashboard preferences, or both. Each export option supports JSON, CSV, and XLSX. Preferences include theme, column visibility, skill overrides, and work-mode badge colors. Exports do not include passwords, sessions, tokens, permissions, admin logs, invite codes, or secrets.

To restore data, open `/export` and drop or click-to-select a `.json`, `.csv`, or `.xlsx` file. Import automatically detects whether the file contains jobs, preferences, or both. Job imports run server-side in a database transaction and imported records are assigned to the currently logged-in user; uploaded files are processed immediately and are not stored permanently.

API endpoints are also available for authenticated users:
- `GET /api/export/`
- `POST /api/import/`

## Seed data
```bash
cd backend
python manage.py seed_demo
```
Creates one active invite code (`FRIEND-DEMO`), five example jobs, two evaluations, and two follow-ups. Admin setup instruction: `python manage.py createsuperuser`.

## Tests and verification

Backend tests:

```bash
pip install -r requirements.txt
cd backend
python -m pytest -q
```

Frontend production build check:

```bash
cd frontend
npm install
npm run build
```

Manual MVP verification checklist:

1. Start backend and frontend using the local setup commands above.
2. Go to `/public-submit`, use invite code `FRIEND-DEMO`, and submit a job with just a URL if desired.
3. Invalid invite code should show a validation error.
4. Log in at `/login` as the owner.
5. Confirm the dashboard loads jobs from the backend.
6. Go to `/prompts`, select the URL-only job, and click `Generate Missing Details Prompt`.
7. Paste ChatGPT `job_updates` JSON into `/import`; confirm company/title/details update.
8. Open a job detail page from the dashboard.
9. Go to `/prompts`, select the submitted job, generate and copy the evaluation prompt.
10. Paste valid ChatGPT-style evaluation JSON into `/import` and import it.
11. Confirm the dashboard/job detail show fit score, priority, recommendation, gaps, and next action.
12. Confirm `/export` downloads JSON, CSV, and Markdown exports.

## Important API endpoints
- `POST /api/public/submit/`
- `GET/POST /api/jobs/`
- `GET/PATCH/DELETE /api/jobs/{id}/`
- `POST /api/prompts/generate/` for evaluation prompts
- `POST /api/prompts/enrich/` for missing-detail prompts
- `POST /api/prompts/bulk-links/` for a list of links that should become jobs plus evaluations
- `POST /api/evaluations/import/` for evaluation JSON, `job_updates` JSON, or bulk `jobs` JSON
- `GET /api/stats/`
- `GET /api/export/jobs.json`, `.csv`, `/api/export/chatgpt-brief.md`
- `DELETE /api/auth/account/` to delete the current account and owned dashboard data

## Data and privacy notes

DACHApply stores the data needed to provide a private job-search dashboard:

- Account username/email and Django password hash.
- Candidate profile, scoring rules, optional structured profile fields, and prompt templates.
- Job leads, URLs, descriptions, salary/language/work-mode fields, application statuses, status dates, follow-up dates, and source metadata.
- Imported/generated evaluations, fit scores, recommendation fields, skills, gaps, notes, and follow-ups.
- Friend-submission relationships and submitted-by metadata when enabled.

Exports are available from the Data page and include the current user's profile/jobs/evaluations/notes/follow-ups plus optional frontend preferences. Invite codes, passwords, sessions, permissions, and other credentials are intentionally excluded from exports.

Users can delete their account from the Data page. Account deletion removes the user, profile, and owned dashboard jobs; evaluations, notes, and follow-ups attached to those jobs are deleted by cascade. Any remaining references created by Django relations are anonymized via nullable user fields.

## Production deployment configuration

DACHApply is configured through environment variables. In production (`DEBUG=False`) the app refuses to start if critical values are missing.

Required production variables:

```text
SECRET_KEY=strong-unique-secret
DEBUG=False
ALLOWED_HOSTS=your-domain.example.com
FRONTEND_URL=https://your-domain.example.com
CSRF_TRUSTED_ORIGINS=https://your-domain.example.com
DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/DBNAME
DEFAULT_FROM_EMAIL=DACHApply <noreply@your-domain.example.com>
EMAIL_HOST=smtp.example.com
```

Recommended production variables:

```text
CORS_ALLOWED_ORIGINS=https://your-domain.example.com
SECURE_SSL_REDIRECT=True
USE_X_FORWARDED_PROTO=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
DB_CONN_MAX_AGE=600
DB_SSL_REQUIRE=True
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=smtp-user
EMAIL_HOST_PASSWORD=smtp-password
```

Abuse protection is enabled with Django REST Framework cache-backed throttles on login, registration, password reset requests, public submissions, and import endpoints. Optional rate-limit overrides:

```text
RATE_LIMIT_LOGIN_IP=10/minute
RATE_LIMIT_LOGIN_ACCOUNT=5/minute
RATE_LIMIT_REGISTER_IP=5/hour
RATE_LIMIT_PASSWORD_RESET_IP=5/hour
RATE_LIMIT_PASSWORD_RESET_EMAIL=5/hour
RATE_LIMIT_PUBLIC_SUBMIT_IP=20/hour
RATE_LIMIT_IMPORT_USER=60/hour
```

Optional hardening after HTTPS is verified:

```text
SECURE_HSTS_SECONDS=31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS=True
SECURE_HSTS_PRELOAD=True
```

See `.env.example` for a full template.

### Deployment checklist

Before public deployment:

1. Set `DEBUG=False`.
2. Generate and set a strong `SECRET_KEY`; never use `dev-only-change-me` publicly.
3. Set `ALLOWED_HOSTS` to the exact production hostnames.
4. Set `FRONTEND_URL` and `CSRF_TRUSTED_ORIGINS` with `https://` origins.
5. Use PostgreSQL via `DATABASE_URL`; do not rely on SQLite for public multi-user production.
6. Set SMTP email variables and test password reset delivery.
7. Keep `SESSION_COOKIE_SECURE=True` and `CSRF_COOKIE_SECURE=True`.
8. Enable `SECURE_SSL_REDIRECT=True` and `USE_X_FORWARDED_PROTO=True` behind a TLS-terminating proxy/load balancer.
9. Run migrations and collect static files.
10. Create a non-shared admin account and use strong passwords.
11. Verify login, CSRF-protected POSTs, export/import, prompt generation, and password reset on the deployed domain.
12. After HTTPS is stable, enable HSTS.
13. Configure database/backups outside the app.
14. Review logs for `DisallowedHost`, CSRF, email, and database connection errors.

## Azure App Service deployment

Use PostgreSQL for public deployment. SQLite can still be used for local testing or throwaway demos only.

Suggested build steps:
```bash
cd frontend
npm install
npm run build
cd ../backend
pip install -r ../requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
```

Startup command:
```bash
cd backend && gunicorn config.wsgi --bind=0.0.0.0:$PORT
```
`gunicorn` is included in `requirements.txt` for this startup command.

Minimum Azure environment variables:
- `SECRET_KEY`
- `DEBUG=False`
- `ALLOWED_HOSTS=your-app.azurewebsites.net`
- `FRONTEND_URL=https://your-app.azurewebsites.net`
- `CSRF_TRUSTED_ORIGINS=https://your-app.azurewebsites.net`
- `DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/DBNAME`
- `SECURE_SSL_REDIRECT=True`
- `USE_X_FORWARDED_PROTO=True`
- SMTP email variables listed above

### Azure cost-control checklist
- Use Free F1 App Service for testing.
- For private throwaway demos only, SQLite can reduce cost; for any public deployment use PostgreSQL via `DATABASE_URL`.
- Disable always-on features not available/free.
- Avoid Application Insights paid ingestion until needed.
- Export backups manually from the app/admin.

## Screenshots
Add screenshots here after running locally:

- Dashboard: searchable/filterable job table with status, priority, and recommendation badges.
- Friend submission form: simple invite-code + URL-first submission page.
- Prompt generator: bulk links area, existing-job selector, selected preview, generated prompt, copy button.
- Import evaluation page: JSON textarea, clear validation errors, success summary listing created/updated jobs.
- Job detail: clean metadata header, badges, fit score card, match/gap cards, next action, raw description, notes.

## Security notes
- Django CSRF/session authentication enabled.
- Owner APIs require authentication by default.
- Public submission requires active invite code and includes a honeypot spam field. The frontend stores the invite code in that browser's localStorage after a successful submission, so trusted friends do not need to retype it every time.
- URLs are validated by serializers/model fields. Common pasted forms such as `https-www.karriere.at-jobs-7794074` are normalized to `https://www.karriere.at/jobs/7794074`.
- Secrets are read from environment variables; use `.env.example` as a template.

## Future improvements
- Azure PostgreSQL
- Azure Blob Storage for backups/exports
- GitHub Actions deployment
- Application Insights logging
- Browser extension for saving jobs
- Optional LLM API mode
- Email reminders
- CV version management
- Recruiter message generator
- Interview preparation module
