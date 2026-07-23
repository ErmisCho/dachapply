---
id: TASK-40
title: Edit original job text and copy calibration prompt
status: Done
assignee:
  - '@pi'
created_date: '2026-07-17 08:14'
updated_date: '2026-07-18 10:33'
labels:
  - frontend
  - backend
  - data
  - ai
dependencies:
  - TASK-30
modified_files:
  - backend/jobradar/views.py
  - backend/jobradar/tests/test_api.py
  - frontend/src/App.tsx
priority: medium
ordinal: 40000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owners can explicitly correct a job's central original text from the job details page and generate/copy a ChatGPT calibration prompt for that job.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Job details provide an editable original-text field initialized from the stored source
- [x] #2 Saving non-empty original text explicitly replaces the immutable imported snapshot for that owned job
- [x] #3 Other users cannot modify the source text
- [x] #4 A calibration button generates and copies a ChatGPT details-plus-evaluation prompt for the job
- [x] #5 The prompt is visible for manual copying when clipboard access fails
- [x] #6 Tests and frontend build pass
- [x] #7 Job details accept pasted ChatGPT calibration JSON and import it through existing validation/conflict handling
- [x] #8 Successful calibration refreshes the displayed job and evaluation
- [x] #9 A button beside Generate + copy calibration prompt pastes the Codex response from the clipboard into the calibration import field
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Keep the existing clipboard-first calibration workflow and add one browser clipboard-read action beside prompt generation; reveal the existing validated import UI with the pasted response.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Added owner-scoped PATCH /api/jobs/:id/source-text/ for deliberate non-empty source correction; it bypasses import immutability only on this explicit action and rejects link-only text. Job details now show a large resizable source editor with save and Generate + copy calibration prompt actions. Calibration saves the latest text first, reuses the combined details/evaluation prompt, attempts clipboard copy, and always displays the prompt as fallback. Other users receive 404. Two focused backend tests, frontend production build, Django check, and whitespace check passed.

Follow-up: add pasted ChatGPT response import to the same calibration section.

Clarified from screenshot: expose a Paste Codex response action directly beside prompt generation instead of requiring the generated prompt section to be open first.

Added Paste Codex response beside prompt generation. It reads clipboard text, reveals the existing calibration JSON field, and keeps manual review plus the existing validated/conflict-aware import flow. Clipboard denial is shown as an actionable error. Frontend production build and diff check pass.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Job details now support the full calibration round trip: edit source, generate/copy a Codex prompt, paste the Codex response from the adjacent button, import it through existing validation, and refresh the job/evaluation.
<!-- SECTION:FINAL_SUMMARY:END -->
