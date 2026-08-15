---
id: TASK-65
title: Migrate Docker and Azure CI to uv and retire requirements.txt
status: To Do
assignee: []
created_date: '2026-08-14 17:45'
labels:
  - infrastructure
  - build
  - tech-debt
dependencies: []
priority: medium
ordinal: 70000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Local development now resolves Python dependencies through uv (pyproject.toml + uv.lock, 21 packages pinned including the full transitive graph). Deployment does not: Dockerfile:19-21 and .github/workflows/deploy-azure.yml:34-35 still `pip install -r requirements.txt`, which pins only direct dependencies by floor (e.g. `pytest>=8.0`, `Django>=5.0,<6.0`) and resolves everything else fresh on every build.

That leaves two declarations of the same dependency set that can drift apart silently, and it means the container is not built from the versions any test run actually exercised. The local rebuild during the TASK-62/uv session resolved pytest 9.1.1 against a `pytest>=8.0` floor - a major version jump that a container build could equally pick up unannounced.

Surfaced on 2026-08-14 while restoring a destroyed .venv. The immediate loss was cheap to repair precisely because uv.lock made the environment reproducible in about four seconds; requirements.txt offers no equivalent guarantee to the deploy path.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The Docker image installs dependencies from uv.lock (e.g. `uv sync --frozen --no-dev`) rather than `pip install -r requirements.txt`
- [x] #2 The Azure deploy workflow installs from the same lockfile, so CI and the image resolve identical versions
- [x] #3 A build fails loudly if uv.lock is out of date with respect to pyproject.toml, rather than silently resolving something newer
- [x] #4 Dev-only dependencies (pytest, pytest-django) are excluded from the production image
- [ ] #5 requirements.txt is deleted, and no file in the repo still references it
- [ ] #6 A container build and a full deploy-workflow run are both verified green before requirements.txt is removed
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
AC1-AC4 DONE (2026-08-15), each verified by running it rather than by reading the config.

Dockerfile: `pip install -r requirements.txt` replaced with `uv sync --locked --no-dev --no-cache`, with uv pinned by digest tag (ghcr.io/astral-sh/uv:0.11.28) so an image rebuild cannot pick up a different resolver. UV_PROJECT_ENVIRONMENT=/usr/local installs into the image's system prefix rather than a .venv, so scripts/start-container.sh keeps calling bare `python` and `gunicorn` with no activation step and needed no change.

`--locked` rather than `--frozen`, which the original AC1 text suggested: --frozen uses the lockfile as-is without checking it against pyproject.toml, so it would satisfy the letter of AC1 while silently allowing exactly the drift AC3 exists to prevent. --locked errors instead.

AC3 verified by deliberately adding an unlocked dependency to pyproject.toml and rebuilding: `error: The lockfile at uv.lock needs to be updated, but --locked was provided` and the build stopped. pyproject.toml was restored afterwards.

AC4 verified inside the built image: all seven runtime imports (Django, gunicorn, dj-database-url, psycopg, whitenoise, DRF, openpyxl) succeed and both pytest and pytest-django are absent.

Beyond the ACs, the image was smoke-tested rather than only built: run with DEBUG=True and a blank DATABASE_URL, it applied migrations and served GET /api/health/ -> {"status":"ok","database":"ok"}. A green build says the dependencies resolve; only running it shows the app still starts.

deploy-azure.yml now installs via astral-sh/setup-uv@v5 plus `uv sync --locked --no-dev`.

AC5 AND AC6 REMAIN OPEN, deliberately. No build or deploy file references requirements.txt any more - only docs - so deleting it looks safe, but the legacy App Service path deploys a zip through azure/webapps-deploy@v3, and App Service's Oryx builder auto-detects a requirements.txt in the archive. Deleting it could therefore change how that deploy builds, in a way no local check reveals. AC6 requires a real deploy run to prove otherwise, and that means a push to main, which triggers deploy-container-apps.yml and ships to production. That is the owner's call, not an agent's.

Interim measure so the two files cannot drift while both exist: requirements.txt is no longer hand-maintained. It is generated from the lockfile with
    uv export --no-dev --no-hashes --no-emit-project --format requirements-txt -o requirements.txt
and now contains 14 fully pinned runtime packages with dev excluded, matching uv.lock exactly. This removes the actual hazard behind this task - two hand-edited declarations diverging - without touching the deploy path. README and pyproject.toml both record that it is generated and must be regenerated after any dependency change.

TO FINISH: merge to main, let deploy-container-apps.yml build and deploy, confirm the app is green, then delete requirements.txt and re-run the legacy App Service deploy if that path is still wanted. If the legacy path is no longer used, deleting deploy-azure.yml along with requirements.txt is the simpler close.

Docs updated to uv: README local setup (`uv sync`, `uv run manage.py migrate`), README test section (`uv run pytest -q`), and AGENTS.md test-command. The documented test command was re-run after the change: 154 passed.
<!-- SECTION:NOTES:END -->
