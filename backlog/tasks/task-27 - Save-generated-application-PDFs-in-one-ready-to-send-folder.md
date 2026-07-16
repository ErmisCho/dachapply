---
id: TASK-27
title: Save generated application PDFs in one ready-to-send folder
status: Done
assignee:
  - '@pi'
created_date: '2026-07-15 15:41'
updated_date: '2026-07-15 15:52'
labels:
  - backend
  - workflow
dependencies:
  - TASK-26
priority: medium
ordinal: 27000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
After successful local generation, save attachment-ready PDFs in one folder and open it so the user can immediately upload files to a career site. Keep TeX sources organized separately. Recommended destination: C:\latex\ready-to-send for PDFs, with CV TeX in C:\latex\CVs\sent and letter TeX in C:\latex\output.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Generated CV PDF and optional letter PDF are copied to C:\latex\ready-to-send
- [x] #2 Generated CV TeX is saved under C:\latex\CVs\sent and optional letter TeX under C:\latex\output
- [x] #3 The ready-to-send folder opens after generation on local Windows
- [x] #4 Existing files are not silently overwritten
- [x] #5 Tests verify output placement and collision handling
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Persist generated artifacts after compilation, use collision-safe names, and open the common PDF folder locally.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Selected one common attachment folder: C:\latex\ready-to-send. Generated CV/letter PDFs are copied there; CV TeX goes to CVs\sent and letter TeX to output. Existing names receive -2, -3, etc. The folder opens through Windows after saving, controlled by a local setting. Persisted paths are retained in task metadata for revisions. Three focused tests and Django checks passed.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Generated application files are now persisted collision-safely, with all upload-ready PDFs in one folder that opens automatically.
<!-- SECTION:FINAL_SUMMARY:END -->
