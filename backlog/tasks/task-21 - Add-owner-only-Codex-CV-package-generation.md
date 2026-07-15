---
id: TASK-21
title: Add owner-only Codex CV package generation
status: Done
assignee:
  - '@pi'
created_date: '2026-07-15 13:57'
updated_date: '2026-07-15 14:52'
labels:
  - backend
  - frontend
  - ai
dependencies: []
priority: high
ordinal: 21000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The configured owner can generate one tailored CV matching the detected job-description language plus one selected letter template. DACHApply must show the detected templates for confirmation before invoking the server-side Codex CLI. Source templates remain private and are never overwritten.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Only the configured owner email can access the generation endpoint and UI
- [x] #2 DACHApply detects English or German from the stored job description and selects the matching CV
- [x] #3 The user confirms the selected CV and exactly one compatible letter template before generation
- [x] #4 Generation works from private templates configured outside the repository and never overwrites source files
- [x] #5 The response downloads generated TeX and compiled PDF files when Codex and LaTeX succeed
- [x] #6 Tests cover authorization, language/template selection, and source-file protection
- [x] #7 CV generation is disabled unless CODEX_CV_ENABLED is true, defaulting on only in local DEBUG mode
- [x] #8 When one job is selected, the owner sees a Generate CV button in the dashboard action bar
- [x] #9 The dashboard Generate CV action opens language, letter, and confirmation controls without leaving the selected job toolbar
- [x] #10 The toolbar action says Generate CV and Motivation Letter; CV and letter are editable dropdowns; no verification checkbox is required; final action says Generate
- [x] #11 English CV allows only the English motivation letter; German CV allows only Motivationsschreiben, Bewerbungsschreiben, and Anschreiben
- [x] #12 Codex receives long job data through stdin and returns structured LaTeX while operating read-only on temporary source copies
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Add an owner-gated CV generation service using a configured private workspace and temporary copies. 2. Add preview and generation endpoints. 3. Add a confirmation panel on job detail. 4. Add focused tests and configuration documentation.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented owner-email authorization, English/German job-description detection, explicit CV/letter confirmation, private-workspace temporary copies, Codex CLI execution, LaTeX compilation, ZIP download, and a 3/hour generation limit. Templates and Codex credentials remain outside the repository. Validation: 102 backend tests passed using SQLite, frontend production build passed, Django system check passed. The existing demo scheduler logs a harmless database-access traceback during pytest startup.

Follow-up: add an explicit local-only feature flag so the online instance remains disabled.

Added CODEX_CV_ENABLED. It defaults to DEBUG, is explicitly true in .env.local.example, explicitly false in .env.azure.example, and is enforced by server-side authorization.

Follow-up from UI screenshot: expose the generator from the selected-job toolbar instead of requiring users to discover it on job detail.

Added an owner-only Generate CV action beside Open when exactly one dashboard job is selected. Frontend production build passed.

Refine the dashboard action based on the annotated screenshot: keep the complete verification flow in place rather than navigating to job detail.

Generate CV now opens an in-place popover in the selected-job toolbar with detected language, selected CV, letter choice, explicit confirmation, generation, and cancel controls. Frontend build passed.

Apply the final interaction copy and controls from the annotated popover screenshot.

Updated copy and controls: toolbar and panel say Generate CV and Motivation Letter; both CV and letter are selectable dropdowns across English/German templates; removed the verification checkbox; final action says Generate. Focused backend tests (4) and frontend build passed.

Constrain letter choices by the selected CV language in both UI and server validation.

Letter dropdown now filters by selected CV language, resets to that language's first valid option when CV changes, and backend validation rejects mismatched combinations. Four focused tests and frontend build passed.

Root cause from real smoke test: Codex resolves the Windows sandbox as read-only, so it cannot edit copied files; passing the full prompt as a command argument is also fragile. Switch to read-only structured output over stdin, then let trusted server code write and compile the returned LaTeX.

Fixed the real local failure. Codex was resolving the Windows workspace as read-only and the long prompt was passed as a command argument. Generation now sends the prompt through stdin, runs Codex read-only, requires schema-validated complete LaTeX output, writes it through trusted Python code, then compiles. Four focused tests, frontend build, and Django checks passed.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Added owner-only one-click generation of one language-matched CV and one user-selected letter. Codex edits temporary copies, latexmk compiles them, and DACHApply downloads a ZIP without modifying private source templates.

Generation is now local-only by default and explicitly disabled in the Azure example configuration.

The generator is now directly discoverable from the dashboard selection toolbar.

The full verification and generation workflow now runs directly from the selected-job action bar.

Final labels and editable template dropdowns now match the requested interaction, with no checkbox.

CV and letter language compatibility is enforced in both UI and backend.

Fixed Windows Codex execution by replacing agent file edits with read-only structured output over stdin.
<!-- SECTION:FINAL_SUMMARY:END -->
