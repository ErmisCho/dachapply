---
id: TASK-28
title: Allow readjusting the latest generated application
status: Done
assignee:
  - '@pi'
created_date: '2026-07-15 15:41'
updated_date: '2026-07-16 14:38'
labels:
  - frontend
  - backend
  - ai
dependencies:
  - TASK-27
modified_files:
  - backend/jobradar/services/cv_generator.py
  - backend/jobradar/services/cv_tasks.py
  - backend/jobradar/views.py
  - backend/jobradar/urls.py
  - backend/jobradar/tests/test_api.py
  - frontend/src/App.tsx
priority: medium
ordinal: 28000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
After generation, the owner can provide follow-up instructions to revise the latest CV and optional letter, recompile them, and overwrite that latest working version without modifying protected templates.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Generation UI accepts revision instructions for the latest job output
- [x] #2 Revision uses the latest generated TeX plus candidate evidence and original job context
- [x] #3 Protected base templates remain unchanged
- [x] #4 Tests cover revision task creation and versioned outputs
- [x] #5 Adjustment instructions are available without an in-memory completed task
- [x] #6 After a server restart, revision discovers the latest persisted job-specific TeX files
- [x] #7 Revision can be queued while another generation is running
- [x] #8 Reasoning effort defaults to medium when the model supports it
- [x] #9 Restart recovery supports legacy output paths and revises whichever generated document types exist
- [x] #10 Each revision overwrites the latest selected TeX/PDF files instead of creating another numbered version
- [x] #11 Browser-stale task IDs never block readjustment after backend task state is lost
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Retain task artifact metadata for immediate revisions; after state loss, discover the latest job-specific TeX files on disk. Queue the same revision pipeline, overwrite those selected working TeX/PDF files, and copy the resulting TeX to the clipboard.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Added owner-only revision instructions after a completed generation. Revisions reuse the latest persisted TeX artifacts and original task configuration/context, run through the same asynchronous model/LaTeX pipeline, and persist collision-safe new files without touching templates. Validation passed: 7 focused backend tests, Django check, and frontend production build. The full API test file reached completion under system Python with 103 passed and one unrelated missing-openpyxl environment failure; the project venv run completed all test progress but did not exit before timeout.

Follow-up: make revisions recover from persisted files rather than depending only on in-memory task state, and default supported model effort to medium.

Adjustment UI is now always visible and has independent loading state, so it can queue against the latest saved files while generation runs. Added owner-only revise-latest endpoint that discovers the newest job-specific CV/letter TeX in C:\latex\CVs and C:\latex\output after process restarts, then reuses candidate evidence, job context, AI settings, compilation, versioning, and clipboard flow. Model effort now defaults to medium whenever supported in single and batch UI. Full validation passed: 112 backend tests, frontend production build, Django check, and whitespace check.

Bug follow-up: restart recovery should find legacy CVs/sent and pre-cleanup gender-marker filenames, and should revise whichever selected document files actually exist instead of failing when only CV or only letter was generated.

Fixed false no-files errors by searching both current C:\latex\CVs and legacy C:\latex\CVs\sent locations, including filenames created before gender-marker cleanup. Restart recovery now automatically revises the selected document types that actually exist, so a CV-only prior generation does not fail merely because the UI also defaults the letter on. Two focused regression tests and Django check passed.

Requirement changed: readjustments should overwrite the latest generated files; initial generation remains collision-safe. Clipboard behavior remains enabled for every completed revision.

Changed revision persistence to overwrite the selected latest TeX and matching PDF in place. Initial generation remains collision-safe, while repeated readjustments no longer create numbered copies. The ready task still reads the overwritten TeX and automatically copies it to the clipboard, with the existing Copy TeX fallback. Two focused tests, Django check, and whitespace check passed.

Bug follow-up: a ready task ID can remain in browser state after backend task memory is gone, causing Completed generation task not found. Route UI readjustments through persisted latest-file recovery unconditionally.

The frontend now routes every readjustment through the persisted latest-file endpoint, even when it still displays a ready in-memory task ID. This removes the stale-ID branch that returned Completed generation task not found after backend restarts. Frontend production build and whitespace check passed.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Readjustments always recover from latest persisted files, overwrite them in place, and copy TeX to the clipboard; stale task IDs and server restarts no longer block the workflow.
<!-- SECTION:FINAL_SUMMARY:END -->
