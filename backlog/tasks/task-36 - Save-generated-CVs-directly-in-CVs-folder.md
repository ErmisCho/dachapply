---
id: TASK-36
title: Save generated CVs directly in CVs folder
status: Done
assignee:
  - '@pi'
created_date: '2026-07-16 11:28'
updated_date: '2026-07-16 11:30'
labels:
  - backend
  - frontend
  - workflow
dependencies:
  - TASK-27
modified_files:
  - backend/jobradar/services/cv_generator.py
  - backend/jobradar/tests/test_api.py
  - frontend/src/App.tsx
priority: medium
ordinal: 36000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Generated CV TeX and PDF files are persisted under C:\latex\CVs and the browser no longer automatically downloads the generated archive. Letter files remain under C:\latex\output.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Generated CV TeX and PDF files are saved collision-safely under C:\latex\CVs
- [x] #2 Generated letter TeX and PDF files remain collision-safely under C:\latex\output
- [x] #3 Completing single generation does not trigger an automatic browser download
- [x] #4 The CV output folder opens after local generation
- [x] #5 Tests and frontend build pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Change the existing persistence destinations and stop the single-generator auto-download; retain explicit download links and ZIP API for recovery.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Changed local persistence so CV TeX/PDF pairs go directly to C:\latex\CVs and letter TeX/PDF pairs go to C:\latex\output, both collision-safe. Local completion opens the CVs folder. Removed the single-generator automatic ZIP navigation while retaining task archives and explicit batch downloads. Two focused backend tests, frontend production build, Django check, and whitespace check passed.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Generated CV files now stay in C:\latex\CVs instead of being automatically downloaded; letters stay in C:\latex\output.
<!-- SECTION:FINAL_SUMMARY:END -->
