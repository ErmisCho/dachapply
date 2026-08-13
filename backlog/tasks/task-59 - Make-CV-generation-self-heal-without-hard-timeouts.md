---
id: TASK-59
title: Make CV generation self-heal without hard timeouts
status: Done
assignee:
  - '@pi'
created_date: '2026-08-13 09:05'
updated_date: '2026-08-13 09:20'
labels:
  - bug
  - cv-generation
  - performance
dependencies: []
modified_files:
  - .env.example
  - backend/config/settings.py
  - backend/jobradar/services/cv_generator.py
  - backend/jobradar/services/cv_tasks.py
  - backend/jobradar/tests/test_api.py
  - frontend/src/App.tsx
priority: high
ordinal: 60000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The live two-job batch using gpt-5.6-sol/xhigh/Fast took over 2.5 minutes and both rows failed during LaTeX compilation, including a hard 120-second compile timeout. Generation should remain cancellable but not kill itself on elapsed time, retry correctable model/LaTeX failures, and present a short actionable error only after repair attempts fail.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Model and LaTeX subprocesses remain cancellable but have no application-imposed wall-clock timeout
- [x] #2 Invalid generated output, LaTeX compilation errors, and page-limit failures trigger automatic model repair and recompilation before the task fails
- [x] #3 A terminal failure shows a concise user-facing summary while retaining useful diagnostics for debugging
- [x] #4 The UI explains that reasoning effort affects generation time and offers a faster practical default
- [x] #5 Focused backend tests and the frontend production build pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Remove application wall-clock cutoffs while preserving cooperative cancellation. 2. Reuse the selected model for up to two repair passes when output validation or LaTeX/page checks fail. 3. Keep full diagnostics server-side/in task data but show a concise error plus repair count. 4. Add a speed hint/default and focused regressions, then run the backend/frontend checks and live compile verification.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Root cause evidence: ordinary copies compile concurrently in about 4-5 seconds, while an orphaned latexmk process from a prior timed-out run remained alive and later logged pdfTeX fflush() failed after its output pipe closed. Removed model/LaTeX wall-clock cutoffs, serialized the short Windows TeX stage, and added two model repair/recompile passes for invalid output, compile errors, and page-limit failures. UI now honors model default effort (low for GPT-5.6-Sol), defaults to Fast where available, explains xhigh latency, and exposes short errors with expandable diagnostics. Validation so far: 5 focused tests, all 129 backend tests, frontend build, Django check, migration check, and diff check passed.

Final live verification: jobs #539 (itestra) and #600 (Frequentis) ran concurrently with GPT-5.6-Sol/low/Fast; both generated CV + letter, compiled, saved, and reached Ready in 86.1 seconds total with zero repair attempts and no leftover model/TeX subprocesses. This is about 43% faster than the reported 2.5-minute run before accounting for the new stripped Codex user/plugin configuration. A minimal --ignore-user-config/--ignore-rules Codex smoke call authenticated successfully. Local health remains 200/database ok.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Removed self-imposed model and LaTeX deadlines while preserving cancellation; serialized Windows TeX compilation and added two automatic model repair/recompile passes. Failures now have concise summaries plus expandable diagnostics. Generation now defaults GPT-5.6-Sol to Low + Fast and avoids unrelated Codex plugins; a real two-job batch completed both packages successfully in 86.1 seconds. All 129 backend tests, focused regressions, frontend build, Django and migration checks pass.
<!-- SECTION:FINAL_SUMMARY:END -->
