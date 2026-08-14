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
- [ ] #1 The Docker image installs dependencies from uv.lock (e.g. `uv sync --frozen --no-dev`) rather than `pip install -r requirements.txt`
- [ ] #2 The Azure deploy workflow installs from the same lockfile, so CI and the image resolve identical versions
- [ ] #3 A build fails loudly if uv.lock is out of date with respect to pyproject.toml, rather than silently resolving something newer
- [ ] #4 Dev-only dependencies (pytest, pytest-django) are excluded from the production image
- [ ] #5 requirements.txt is deleted, and no file in the repo still references it
- [ ] #6 A container build and a full deploy-workflow run are both verified green before requirements.txt is removed
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Do not delete requirements.txt before AC6 passes - it is currently the only thing feeding the container build and the Azure deploy, so removing it early breaks production deployment rather than just local tooling.

The dev/runtime split already exists in pyproject.toml: runtime dependencies sit under [project.dependencies], and pytest/pytest-django under [dependency-groups].dev, so `uv sync --frozen --no-dev` should already produce the right production set. `[tool.uv] package = false` is set because the repo is an application, not an installable library.
<!-- SECTION:NOTES:END -->
