# Debug session: no-change CV revisions launch full generation
Created: 2026-09-01T22:24:00Z
Session: task-213-2026-09-01-performance

## Phase 1 — Root Cause

### Error

Observed behavior: clicking `Readjust and compile` with instructions beginning `No further CV changes required.` starts the normal model/compile task and can run for minutes; no exception or nonzero exit is emitted.

### Reproduction

1. Select Salesforce job 1382, which has an existing 11,352-byte generated TeX artifact.
2. Enter the supplied no-change confirmation and click `Readjust and compile`.
3. Trace `POST /api/jobs/1382/cv-generation/revise-latest/` through `revise_latest_cv_documents`.

Environment: Windows localhost runtime at released `9d5c7a56add5d8d7d3f4c8c17d30264c9657f396`; frequency: always for every non-empty instruction.

### Suspect commits

- `5611529 feat: complete remaining backlog workflows (#88)` — introduced the revision workflow's unconditional non-empty-instruction path.
- Later CV changes preserve this route; `a364917` only bounds popup model discovery and does not affect revision execution.

### Instrumentation data

- Boundary 1: request text is non-empty, so the generic validation accepts it.
- Boundary 2: `revise_latest_cv_documents` performs model validation and candidate-evidence loading for all accepted text.
- Boundary 3: it unconditionally calls `start_cv_task(... revision_instructions=...)`.
- Boundary 4: `_run` unconditionally calls `generate_cv_package`, then learns a preference and compiles artifacts.
- The Salesforce owner currently has a generated CV source; no letter source is present.

### Hypothesized root cause

The revision boundary equates every non-empty instruction with a requested document mutation and has no explicit no-change terminal state. · Confidence: high

## Phase 2 — Pattern

The same class appears in both entry points: recovered latest-file revision in `views.revise_latest_cv_documents` and in-memory revision in `cv_tasks.start_cv_revision`. A regression must cover both so one route cannot continue launching the model.

## Phase 3 — Impact

Affected files/callers:
- `backend/jobradar/views.py`: recovered latest-file endpoint and owner/artifact checks.
- `backend/jobradar/services/cv_tasks.py`: in-memory completed-task revision entry point.
- `backend/jobradar/tests/test_api.py`: API and task regressions.

Real mutation instructions and every correction-image request must remain on the existing generation path. No frontend change is necessary if the backend returns an already-ready task in the existing response shape.

## Phase 4 — Solution

Recognize only an unambiguous first statement equal to `No further CV changes required`; reject the shortcut whenever a correction image is present. For a recovered latest-file request, create an already-ready task from the owner's existing artifacts without model/compiler work. For an in-memory completed task, return that same ready task. Add focused timing, ownership, real-edit, and image regressions.

## Resolution

Added an exact first-statement no-change classifier and an already-ready task containing the owner's unchanged existing artifacts. Restart-recovered revisions create that ready task; in-memory revisions reuse their ready parent. Correction images and real edits retain the original generation path. Focused tests passed (3 direct, 28 CV/evidence tests). Released SHA `4e86f15466f4c086c777267ae02bb818bd449692` completed the owner endpoint in 182.93 ms, returned ready with the same CV TeX/PDF, preserved the source SHA-256, and measured 0 database writes, 0 model calls, and 0 compiler calls. Main CI/deployment run `33566678270` passed.
