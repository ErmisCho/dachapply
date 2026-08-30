---
id: TASK-205
title: Open the local app from the backend root URL
status: In Progress
assignee:
  - '@pi'
created_date: '2026-08-30 14:11'
updated_date: '2026-08-30 14:28'
labels:
  - bug
  - local-dev
dependencies: []
modified_files:
  - backend/config/urls.py
  - backend/jobradar/tests/test_settings.py
  - .claude/.asian-dad/task-205-local-root-rubric.json
  - .orchestrator/debug/task-205-2026-08-30-bugfix-1-1.md
  - .orchestrator/debug/task-205-2026-08-30-bugfix-1-2.md
  - .orchestrator/debug/task-205-2026-08-30-bugfix-1-3.md
  - .orchestrator/debug/task-205-2026-08-30-bugfix-2-1.md
  - .orchestrator/debug/task-205-2026-08-30-bugfix-2-2.md
  - backlog/tasks/task-205 - Open-the-local-app-from-the-backend-root-URL.md
priority: high
ordinal: 204000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Normal local startup runs Django on port 8000 and Vite on port 5173, but visiting the obvious backend root currently shows Django's DEBUG 404 page because the disposable runtime has no frontend/dist. Make the local root route users to the running frontend without changing production routing, API/admin behavior, remote-database safeguards, or active development worktrees.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 With DEBUG enabled and frontend/dist absent, GET / returns a temporary redirect to the configured local frontend URL
- [ ] #2 API, admin, static, and production SPA routing retain their existing behavior
- [ ] #3 A regression test covers the missing-dist local root behavior
- [ ] #4 The released local runtime and deployed main pass their required checks
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Preserve the Phase 1 root-cause evidence and sealed evaluator rubric. 2. Add an exact DEBUG-only root redirect to the already-configured frontend URL only when the built frontend is absent, leaving existing production SPA/API/admin/static routing unchanged. 3. Add focused URLconf regression coverage with state restoration. 4. Run focused and full quality gates, evaluate, merge, verify released runtime/deployment, and close the task.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Root cause documented in .orchestrator/debug/task-205-2026-08-30-bugfix-1-1.md: the disposable runtime runs Vite without frontend/dist, while Django only registers its frontend route when that directory exists. Fresh measurements: port 8000 root=404, port 5173 root=200.

Implemented the minimal DEBUG/missing-dist root redirect without touching launcher, API, admin, static, production SPA, or database behavior. Added a URLconf test that isolates and restores settings/module state.

Verification: focused 5 passed; full backend 1028 passed; frontend 195 passed; production build, Django check, compileall, diff check, and npm audit passed. Alternate-port HTTP proof: 302 Location http://localhost:5173, followed by HTTP 200 DACHApply. Asian Dad self-evaluation: PERFECT (all four sealed criteria passed with measured evidence).
<!-- SECTION:NOTES:END -->
