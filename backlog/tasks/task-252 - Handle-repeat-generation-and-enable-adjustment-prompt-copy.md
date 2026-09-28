---
id: TASK-252
title: Handle repeat generation and enable adjustment prompt copy
status: In Progress
assignee:
  - '@pi'
created_date: '2026-09-28 14:12'
updated_date: '2026-09-28 14:29'
labels: []
dependencies: []
modified_files:
  - .orchestrator/debug/01a0e859-192d-77f4-aed0-df74ffce7244-1.md
  - frontend/src/cvSelection.test.ts
  - frontend/src/cvModel.ts
  - frontend/src/App.tsx
  - backend/jobradar/tests/test_api.py
  - backend/jobradar/views.py
  - frontend/src/cvPopup.test.tsx
type: bug
ordinal: 250000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The generation dialog can show 'Failed to fetch' even though matching generated files remain visible. Before replacing files generated with the same selected settings, ask the user to confirm regeneration. The Adjust latest files area must also provide a usable copy action for the prompt/content that should be pasted into ChatGPT for manual adjustment.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 When matching output files already exist for the selected generation settings, Generate asks whether to recreate them before starting generation
- [x] #2 Cancelling the confirmation leaves the existing generated files untouched and does not start a generation request
- [x] #3 Confirming regeneration starts the existing generation flow
- [x] #4 The Adjust latest files copy action is clickable whenever generated source files are available and copies the manual ChatGPT adjustment payload
- [x] #5 Relevant frontend tests cover repeat-generation confirmation and copy availability
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Add the canonical generated-TeX clipboard payload to the existing owner-only preview response.
2. Gate single-job regeneration with native confirmation when a selected output already exists, and source Copy TeX from task or preview state through the shared clipboard helper.
3. Add focused backend and DOM-free frontend regression tests, then run project quality gates.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Root cause recorded in .orchestrator/debug/01a0e859-192d-77f4-aed0-df74ffce7244-1.md: persisted preview artifacts were disconnected from overwrite confirmation and clipboard state.

User confirmed the displayed 'Failed to fetch' occurred because the backend server was not running; the requested overwrite confirmation and restart-safe copy action remain the implementation scope.

Verification passed:
- backend: uv run pytest -q — 1231 passed
- frontend: npm test — 301 passed
- frontend build: npm run build — passed
- focused regression checks: 24 frontend tests and 6 backend clipboard/preview tests passed
- git diff --check — passed
- Asian Dad eval — PERFECT

Implementation commit: 0ee4177.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Added a pre-generation recreate confirmation for selected outputs and restored Copy TeX from persisted preview files after reopening. The preview now returns the same URL-prefixed ChatGPT payload as completed tasks, and the button uses the shared clipboard fallback. Verified by full backend/frontend suites, production build, focused regression tests, and Asian Dad PERFECT.
<!-- SECTION:FINAL_SUMMARY:END -->
