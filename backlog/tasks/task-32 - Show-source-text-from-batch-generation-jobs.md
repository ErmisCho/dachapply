---
id: TASK-32
title: Show source text from batch generation jobs
status: Done
assignee:
  - '@pi'
created_date: '2026-07-16 10:36'
updated_date: '2026-07-16 10:40'
labels:
  - frontend
  - ux
dependencies:
  - TASK-31
modified_files:
  - frontend/src/App.tsx
  - frontend/src/types/index.ts
priority: medium
ordinal: 32000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
In the multi-job CV generation dialog, each position title links to job details and hovering it reveals the stored original scraped job text in a compact resizable panel.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Each position title in the batch dialog links to its job details page
- [x] #2 Hovering or focusing the title reveals the original source text with editable-description fallback
- [x] #3 The source preview is scrollable and user-resizable
- [x] #4 Frontend production build passes
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Use the source text already returned with each Job and native CSS resize; add no endpoint or popup library.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
The batch dialog now renders each position title as a details-page link. Hovering or keyboard-focusing it shows original_source_text, falling back to raw_description, in a native scrollable/resizable preview. Frontend production build and git diff check passed.

Final pre-commit validation passed: 109 backend tests, Django system check, migration drift check, frontend production build, and whitespace check with CRLF treated as end-of-line.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Batch-generation job titles now link to details and expose their stored scraped text in a compact resizable hover/focus preview.
<!-- SECTION:FINAL_SUMMARY:END -->
