---
id: TASK-366
title: Keep repeatable browser smoke tests for cloud retry and usage-limit recovery
status: Done
assignee: []
created_date: '2026-11-11 14:46'
updated_date: '2026-11-12 13:47'
labels:
  - testing
  - frontend
  - backend
dependencies: []
priority: medium
type: task
ordinal: 366000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
TASK-359/360 were verified using temporary visible-browser harnesses against disposable SQLite/workspaces. Preserve the smallest repeatable checks for those user-facing recovery paths using existing browser tooling. Current npm test runs Vitest; separate frontend/tests browser scripts are not the queue-recovery checks. Reuse established fixtures and scheduler behavior; never require paid model calls, owner credentials, production data or the real CV workspace. A future CI wiring change requires owner approval before merge.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A documented command launches disposable local data/workspace and drives the real frontend and Django routes without paid provider calls or access to owner data.
- [x] #2 The browser saves/reloads the analysis time limit, observes Finding models with elapsed time, and uses one-time cloud retry without changing the saved cloud-only switch.
- [x] #3 A simulated provider usage limit renders one short sanitized line; the same task automatically becomes running at an accelerated reset with identical inputs, and the panel cancellation control works.
- [x] #4 Assertions fail when the load-bearing UI/API recovery behavior is broken; deterministic fixture cancellation and cleanup prevent hanging workers or leftover servers.
- [x] #5 The checks run repeatably twice on the supported development host and in their intended CI environment; failures retain a concise diagnostic artifact. Any required CI-gate edits are approved before merge.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Add an isolated Django fixture launcher and Playwright recovery script using real routes and fake service providers. 2. Verify recovery assertions twice and retain temporary failure diagnostics. 3. Run focused and full checks and record evidence without changing status or AC boxes.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
TASK-366: Added frontend/tests/queue-recovery.mjs, its private queue-recovery-backend.py fixture, queue-recovery.md instructions and npm run test:recovery. Uses real frontend/Django routes, disposable SQLite/workspace/evidence/rules, faked service providers, real sanitizer/reset scheduler, cooperative cancellation, same-task/input assertions, temporary diagnostics and bounded process cleanup. No production code, auth, secrets or .github changes. Status and AC boxes intentionally unchanged.

AC coverage implemented (not browser-verified): #1 documented command and isolated launcher; #2 profile save/reload, discovery elapsed text and one-time cloud retry preserving preference; #3 sanitized limit line, real automatic reset, identical inputs and panel cancel; #4 load-bearing assertions, worker gates/timer/process cleanup and failure diagnostics; #5 two attempts made but both blocked; Linux CI and successful host repeats remain unverified. CI wiring is deferred pending owner approval after TASK-365. No PERFECT evaluation claimed.

Verification:
- node --check frontend/tests/queue-recovery.mjs: PASS (1 syntax check).
- python -c "import ast,pathlib;ast.parse(pathlib.Path('frontend/tests/queue-recovery-backend.py').read_text())": PASS (1 syntax check).
- git diff --check: PASS.
- cd frontend; npm run test:recovery: 0 passed / 1 failed before test load (sandbox Node worker spawn EPERM).
- cd frontend; node --test --test-isolation=none tests/queue-recovery.mjs (twice): each 0 passed / 1 failed (Playwright package missing). Diagnostics retained in system temp dachapply-recovery-V7hgb3 and dachapply-recovery-RQk6ja.
- cd frontend; npx tsc --noEmit: blocked (TypeScript missing; registry cache unavailable); npm test: blocked (Vitest missing), 0 tests executed.
- cd frontend; npm ci --ignore-scripts --no-audit --no-fund (npm cache under system temp): blocked ENOTCACHED; no registry access.
- cd backend; uv run pytest -q --tb=line -p no:cacheprovider jobradar/tests/test_analysis_lanes.py jobradar/tests/test_application_prep_queue.py: blocked before collection (uv cache permissions, then dependency download/network denied with UV_CACHE_DIR under system temp).
- cd backend; python -m pytest -q --tb=line -p no:cacheprovider jobradar/tests/test_analysis_lanes.py jobradar/tests/test_application_prep_queue.py: 0 passed / 58 setup errors, all system-temp permission failures. Retry with --basetemp=$env:TEMP/task366-focused-<unique GUID> had the same 58 setup errors and session cleanup permission failure.
- cd backend; uv run pytest -q --tb=line -p no:cacheprovider (full suite once, UV_CACHE_DIR under system temp and UV_OFFLINE=1): blocked before collection by missing Playwright dependency in offline cache; 0 tests executed.
- Direct disposable launcher startup with system Python: blocked by inability to open SQLite in system temp. The subprocess was waited/cleaned; no server survived.

Remaining: install dependencies on an unrestricted development host, run smoke twice and backend/frontend required checks, then run the identical browser command on intended Linux CI infrastructure. No commit, push or merge performed per explicit task rules.
2026-11-13 (coordinator): 3 consecutive green local runs (Windows, installed Chrome); disabling the usage limit makes it fail; ports 4396/8396 freed after runs. AC5 open: the CI job is not wired - that is a CI-gate change needing owner approval.
2026-11-13: parallel CI job `smoke` (PRs touching backend/frontend/workflows) passed on ubuntu: 1 test, 34 s, job 1m08s; does not lengthen the 6-min test job.
<!-- SECTION:NOTES:END -->
