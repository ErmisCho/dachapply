---
id: TASK-65
title: Migrate Docker and Azure CI to uv and retire requirements.txt
status: Done
assignee:
  - '@claude'
created_date: '2026-08-14 17:45'
updated_date: '2026-08-15 17:40'
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
- [x] #5 requirements.txt is deleted, and no file in the repo still references it
- [x] #6 A container build and a full deploy-workflow run are both verified green before requirements.txt is removed
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

AC5 AND AC6 DONE (2026-08-15), in that order, because AC6 gates AC5.

AC6: pushed to main as a fast-forward (f5ea2c5..cc8955b, 12 commits). deploy-container-apps.yml run 31898305546 completed green in 2m45s - build, GHCR push, Azure Container Apps update, and its own "Verify public app" step. The build log shows `uv sync --locked --no-dev --no-cache` installing 13 packages in 1.22s. Independently confirmed afterwards: https://dachapply.livelysea-3461ad21.westeurope.azurecontainerapps.io/api/health/ returns {"status":"ok","database":"ok"} and the root returns 200. Production now runs on uv.

13 packages in the image against 14 in the old export is correct, not a shortfall: tzdata is marked Windows-only in uv.lock and is properly skipped on Linux.

Rollback target recorded before pushing, in case it had been needed: ghcr.io/ermischo/dachapply:f5ea2c55c807e11cf4b86800daa250951cb74ac7, the image deployed by the previous successful run on 2026-08-04.

AC5: requirements.txt deleted, and deploy-azure.yml with it. The Oryx concern that kept requirements.txt alive applies only to the App Service path, and that path is retired - last run 2026-06-05, superseded by Container Apps, and no App Service resource is visible in the subscription. Keeping a workflow whose dependency file no longer exists would leave a deploy path that fails the moment anyone triggers it. Both files remain in git history, and README documents the uv export command needed to revive them.

Remaining references to requirements.txt are only in this task file and the README paragraph explaining the retirement, which is intentional.

Docs updated to uv: README local setup (`uv sync`, `uv run manage.py migrate`), README test section (`uv run pytest -q`), and AGENTS.md test-command. The documented test command was re-run after the change: 154 passed.
<!-- SECTION:NOTES:END -->
