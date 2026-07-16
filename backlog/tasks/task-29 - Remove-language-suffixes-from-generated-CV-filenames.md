---
id: TASK-29
title: Remove language suffixes from generated CV filenames
status: Done
assignee:
  - '@pi'
created_date: '2026-07-15 15:41'
updated_date: '2026-07-16 06:50'
labels:
  - backend
  - ux
dependencies:
  - TASK-28
modified_files:
  - backend/jobradar/services/cv_generator.py
  - backend/jobradar/tests/test_api.py
priority: low
ordinal: 29000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Generated CV filenames remain target-specific but do not end with EN, DE, English, German, or another language marker.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Generated CV filenames contain candidate, company, and role identifiers without a language suffix
- [x] #2 Letter filenames also avoid automatic language suffixes
- [x] #3 Collision handling still preserves prior files
- [x] #4 Tests verify English and German filename output
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Remove language suffixes in the shared target-name helper and add one focused English/German regression test.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Removed language markers from the shared CV and letter target-name helper. Existing collision-safe persistence remains unchanged. Validation passed: English/German naming regression test, collision/persistence generation test, Django check, and git diff check.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Generated CV and letter filenames now identify the candidate, company, and role without language suffixes; collision versioning remains intact.
<!-- SECTION:FINAL_SUMMARY:END -->
