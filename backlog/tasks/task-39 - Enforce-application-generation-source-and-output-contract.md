---
id: TASK-39
title: Enforce application-generation source and output contract
status: Done
assignee:
  - '@pi'
created_date: '2026-07-17 06:42'
updated_date: '2026-07-17 06:52'
labels:
  - backend
  - ai
  - quality
dependencies:
  - TASK-25
  - TASK-28
modified_files:
  - backend/jobradar/services/cv_generator.py
  - backend/jobradar/services/cv_tasks.py
  - backend/jobradar/tests/test_api.py
  - frontend/src/App.tsx
priority: high
ordinal: 39000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Initial generation and readjustment receive all required source documents in explicit priority order, enforce honesty and page limits, include current files plus visual context for layout revisions, and return structured change/validation summaries.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Prompt explicitly includes the required source-priority and honesty rules
- [x] #2 Initial generation receives evidence, adaptation rules, profile notes, complete original job text, and current instructions
- [x] #3 Readjustment additionally receives every selected current TeX file and current PDF screenshots or compile metadata for layout-related requests
- [x] #4 Missing evidence, rules, original job text, or selected readjustment targets fails clearly
- [x] #5 Compilation failure, CV over 2 pages, and letter over 1 page fail clearly
- [x] #6 Structured output lists changed files, main changes, unsupported requirements not claimed, and required final confirmations
- [x] #7 Readjustments require minimal targeted edits and preserve prioritized experience
- [x] #8 Focused and full validation pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Extend the existing shared prompt/schema and generator only: validate source text, copy/render prior PDFs for layout revisions, enforce page counts with pdfinfo, and require structured summaries. Avoid a second AI pass.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented explicit source priority, honesty, minimal-readjustment, preservation, and cut-order instructions in the shared model prompt. Initial and revised prompts include current instructions and complete original job text; shared context already contains evidence, mandatory rules, and profile notes. Readjustments require selected TeX sources. Layout-related instructions inspect current PDFs with pdfinfo and render readable PNG pages with pdftoppm when available. Structured schema/report now requires changed files, main changes, unsupported requirements not claimed, and all requested confirmations; reports appear in single/batch dialogs and generation-report.json. Backend rejects missing original text/targets, invalid TeX or trailing content, compilation failure with diagnostics, CVs over 2 pages, and letters over 1 page. Validation passed: 113 full backend tests plus page-limit regression, frontend production build, Django check, migration drift check, and whitespace check.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Generation/readjustment now follows the complete source-priority and honesty contract, receives persisted TeX and layout context when needed, emits visible structured reports, and enforces compilation plus 2-page CV/1-page letter limits.
<!-- SECTION:FINAL_SUMMARY:END -->
