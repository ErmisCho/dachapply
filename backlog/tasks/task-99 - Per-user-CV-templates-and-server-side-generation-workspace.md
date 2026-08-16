---
id: TASK-99
title: Per-user CV templates and a server-side generation workspace
status: To Do
assignee: []
created_date: '2026-08-16 00:43'
labels:
  - multi-user
  - cv-generation
  - backend
dependencies:
  - TASK-74
  - TASK-83
priority: low
ordinal: 104000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The last increment of multi-user CV generation, filed now so the plan is not lost, deliberately deferred until a second CV user actually exists.

Today the LaTeX templates are the owner's personal files resolved from a machine-local workspace (backend/jobradar/services/cv_generator.py:102-117; `C:\latex` default at backend/config/settings.py:62), generation serializes on a global compile lock (cv_generator.py:31), and `CODEX_CV_ENABLED` defaults to DEBUG-only (settings.py:56) — so CV generation is local-only by design. TASK-74 (per-user evidence) and TASK-83 (capability flag + filenames) deliver most of the multi-user value on the owner's machine first; this task is what remains for generation to run on the server for anyone.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A second (non-owner) user can generate a CV package with no files from the owner's machine involved
- [ ] #2 Templates are stored and selected per user
- [ ] #3 Concurrent generations by different users do not serialize on a global lock
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Do not start this before TASK-74 and TASK-83 are done and a real second CV user is asking — the server-side workspace (LaTeX toolchain in the container, per-user temp dirs, output storage) is the expensive part and is worthless until then.
<!-- SECTION:NOTES:END -->
