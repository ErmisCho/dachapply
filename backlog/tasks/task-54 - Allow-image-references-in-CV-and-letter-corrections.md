---
id: TASK-54
title: Allow image references in CV and letter corrections
status: Done
assignee:
  - '@pi'
created_date: '2026-07-28 12:11'
updated_date: '2026-08-12 16:16'
labels: []
dependencies: []
modified_files:
  - backend/config/settings.py
  - backend/jobradar/services/cv_generator.py
  - backend/jobradar/services/cv_tasks.py
  - backend/jobradar/views.py
  - backend/jobradar/tests/test_api.py
  - frontend/src/App.tsx
priority: high
ordinal: 55000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Let users keep typing correction instructions while also pasting or dragging and dropping a screenshot/image into the CV or letter readjustment area. The image should be sent only for that correction and made available to the selected model as visual context.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The single-job and batch correction controls accept an image from clipboard paste or drag and drop without replacing typed instructions
- [x] #2 Users can preview and remove the selected image before submitting
- [x] #3 A correction can be submitted with text, an image, or both, while still requiring at least one document
- [x] #4 The backend rejects malformed, unsupported, or oversized images and does not persist uploaded correction images
- [x] #5 The selected model receives the validated image as correction context; backend tests and frontend build pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Add minimal data-URL image validation and temporary-file handoff to CV generation. 2. Allow image-only revisions through task/view validation. 3. Add native paste/drop/file selection UI with preview/remove in single and batch correction controls. 4. Add focused tests and run project checks.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented native paste/drop/file selection with preview/removal in single and batch correction controls. The backend validates PNG/JPEG/WebP data URLs up to 5 MB, keeps bytes only in task memory and a TemporaryDirectory, attaches the temporary file to Codex with --image (Claude receives it through its Read tool), and supports image-only revisions. Validation: 127 backend tests passed; frontend production build passed; makemigrations --check found no changes; py_compile and git diff --check passed.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Added temporary visual correction context for single-job and batch CV/letter readjustments, including text+image/image-only submission, preview/removal, backend format/size validation, model handoff, and cleanup. Verified with the full backend suite and frontend production build.
<!-- SECTION:FINAL_SUMMARY:END -->
