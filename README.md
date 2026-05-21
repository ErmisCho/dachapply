# DACHApply

This is a full-stack Django and React application for collaborative job lead collection, structured job evaluation, manual ChatGPT-based analysis, and application prioritization.

## Purpose
DACHApply is a private job intelligence dashboard for a Software Engineer job search in Austria/Germany. Friends can submit relevant job links using invite codes. The owner reviews leads, generates reusable ChatGPT prompts without paid LLM APIs, imports strict JSON evaluations, and tracks applications, notes, and follow-ups.

## Architecture
- `backend/`: Django, Django REST Framework, SQLite, Django auth/admin, pytest tests
- `frontend/`: React + TypeScript + Tailwind CSS (Vite)
- Production later: PostgreSQL-compatible environment variable hooks, but SQLite works for MVP and Azure App Service Free testing
- React production build is served by Django/WhiteNoise

## Core workflow
1. Friend opens `/public-submit`, enters invite code once, and may submit either full job details or just a job URL. After a successful submission, the browser remembers the invite code for next time.
2. Owner logs in at `/login` and views dashboard.
3. Owner can paste a list of job links in `/prompts` and generate a Bulk Links Prompt for ChatGPT. The returned JSON can create new jobs with details and nested evaluations.
4. Owner can also select URL-only/incomplete existing jobs in `/prompts` and generate a Missing Details Prompt for ChatGPT.
5. Owner pastes ChatGPT's `job_updates` or `jobs` JSON into `/import`; the app updates or creates the correct job records.
6. Owner selects completed jobs in `/prompts` and generates an Evaluation Prompt with embedded candidate profile.
7. Owner pastes strict evaluation JSON into `/import`.
7. Backend validates required fields and stores `JobEvaluation` records.
8. Dashboard/job detail pages show score, priority, recommendation, gaps, status, next action.

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
- Exports: `http://localhost:5173/export`
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

## Azure App Service Free deployment
SQLite is acceptable for the first free MVP deployment. PostgreSQL can be added later when moving beyond free testing.

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

Environment variables:
- `SECRET_KEY`
- `DEBUG=False`
- `ALLOWED_HOSTS=your-app.azurewebsites.net`
- `CSRF_TRUSTED_ORIGINS=https://your-app.azurewebsites.net`
- `DB_NAME=/home/site/wwwroot/backend/db.sqlite3` (adjust if needed)

### Azure cost-control checklist
- Use Free F1 App Service for testing.
- Keep SQLite for MVP; avoid paid Azure PostgreSQL initially.
- Disable always-on features not available/free.
- Avoid Application Insights paid ingestion until needed.
- Export backups manually from the app/admin.

## Screenshots
- Dashboard: _placeholder_
- Friend submission form: _placeholder_
- Prompt generator: _placeholder_
- Import evaluation page: _placeholder_
- Job detail: _placeholder_

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
