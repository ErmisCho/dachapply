---
id: TASK-253
title: 'Make CV generation job-specific, replaceable, and editable'
status: In Progress
assignee:
  - '@pi'
created_date: '2026-09-28 15:19'
updated_date: '2026-09-28 16:13'
labels: []
dependencies: []
references:
  - 'https://github.com/ErmisCho/dachapply/pull/186'
modified_files:
  - .orchestrator/debug/01a0e859-192d-77f4-aed0-df74ffce7244-2.md
  - backend/jobradar/tests/test_api.py
  - frontend/src/cvSelection.test.ts
  - frontend/src/cvPopup.test.tsx
  - backend/jobradar/services/cv_generator.py
  - backend/jobradar/services/cv_tasks.py
  - backend/jobradar/views.py
  - frontend/src/cvModel.ts
  - frontend/src/App.tsx
  - backend/jobradar/management/commands/report_cv_prompt_size.py
type: enhancement
ordinal: 251000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
CV generation must operate on the current job rather than ambiguous filenames: detect prior files for that job, confirm and update selected outputs, and name letters by their selected type. The popup must also clearly flag an unknown company and let the user correct the company and source job text before generating.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Generated files are matched to the specific job so files for another position do not trigger replacement or get overwritten
- [x] #2 When selected files already exist for the job, generation asks for confirmation before starting
- [x] #3 After confirmation, generation updates the existing selected files instead of creating another numbered copy
- [x] #4 Cancelling confirmation leaves existing files unchanged and sends no generation request
- [x] #5 A generated letter filename uses the selected letter template label or key, such as Anschreiben, instead of Letter
- [x] #6 Legacy generated filenames remain discoverable for readjustment and copy
- [x] #7 Backend and frontend regression tests cover job matching, replacement, confirmation, and letter naming
- [x] #8 The generation popup visibly identifies a missing or placeholder company as unknown
- [x] #9 The user can edit and save the company and source job text from the generation popup before generating
- [x] #10 Generation after saving uses the corrected company and source job text
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Pin current filename matching, replacement, legacy lookup, and popup-save behavior with focused backend/frontend regressions.
2. Add job-ID-scoped output names, template-labelled letters, selected-template artifact discovery, and confirmed in-place replacement while retaining legacy lookup.
3. Reuse the source-text PATCH route to atomically save popup company + source text, then expose editable fields and unknown-company warning before generation.
4. Run focused tests, full backend tests, frontend tests/build, strict evaluation, then commit, push, merge, and close the task.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Root cause reproduced and documented in .orchestrator/debug/01a0e859-192d-77f4-aed0-df74ffce7244-2.md: output identity omits job ID and fresh persistence always allocates a numbered path.

Added failing backend regressions for job-ID and letter-template naming, selected-source lookup, replacement confirmation, in-place persistence, and atomic company/source updates.

Implemented job-ID-scoped names, template-labelled letters, exact numbered-copy matching, per-template artifact discovery, legacy fallback, and confirmed replacement targets.

Generation now rejects silent replacement, forwards explicit replacement intent, and source-text PATCH atomically saves validated company plus source text.

Single and batch generation now confirm selected job/template outputs, send replacement intent, and recompile the selected letter. The single popup adds unknown-company warning plus editable/savable company and job text, with generation blocked while edits are unsaved.

Included job ID in cache identity (cache v5) so equal-looking jobs cannot reuse one another's cached artifact paths.

Full backend gate: 1,228 passed / 5 failed. Root causes recorded: outdated lookup mock arity, generic-Letter-dependent page-count fake, and unnecessary replace_existing=False keyword.

Corrected verification doubles to accept selected-letter lookup and identify CVs by the stable -CV- marker; unchanged task starts no longer receive replacement kwargs.

Added an end-to-end route regression proving generation starts from the company and source text atomically saved by the popup.

Job-scoped lookup now keys on applicant + document type + immutable job ID while allowing the readable company/title slug to change after popup edits.

Made the replacement decision executable in unit tests: decline returns the cancel sentinel, no files skips confirmation, and approval returns replacement intent; App still returns before the request.

Final verification: 1,234 backend tests passed; 306 frontend tests passed; production TypeScript/Vite build passed; git diff --check passed; Asian Dad returned PERFECT. Visible Chrome verification on an isolated SQLite database showed the unknown-company warning, editable company/job text, Generate disabled while dirty, successful atomic save, corrected values, warning removal, and Generate re-enabled.

Implementation PR: #186.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Made generated outputs job-specific with immutable job IDs, exact selected-template matching, explicit replacement confirmation, in-place overwrite, template-labelled letter filenames, legacy discovery, and job-aware cache identity. Added atomic popup editing for company and source text with a visible unknown-company warning and dirty-state generation guard. Verified with 1,234 backend tests, 306 frontend tests, a production frontend build, visible browser interaction, and Asian Dad PERFECT.
<!-- SECTION:FINAL_SUMMARY:END -->
