---
id: TASK-384
title: 'Adjust offers CV, letter or both once both documents exist'
status: Done
assignee: []
created_date: '2026-11-17 10:13'
updated_date: '2026-11-19 06:34'
labels: []
dependencies: []
priority: medium
ordinal: 385000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner request 2026-11-17: when a job first got only one document (CV or letter) and the other type is generated later, the Adjust panel must offer CV, letter or both, with both selected by default.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 After the second document type is generated for a job that had only one, Adjust shows CV and letter options without a page reload
- [x] #2 Both are selected by default; the owner can untick either one
- [x] #3 A job with only one generated document still offers only that one
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
PR #426. Verified on localhost 2026-11-19 (runtime a081242, bundle index-DwwR4cEt.js matches dist). Job 2086: Adjust shows CV and Letter, both ticked; job 2024 (CV only): only the CV is pre-selected for Adjust.
<!-- SECTION:NOTES:END -->
