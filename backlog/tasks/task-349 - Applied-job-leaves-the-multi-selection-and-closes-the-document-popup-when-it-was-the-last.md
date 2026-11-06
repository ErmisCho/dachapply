---
id: TASK-349
title: >-
  Applied job leaves the multi-selection and closes the document popup when it
  was the last
status: Done
assignee: []
created_date: '2026-11-05 19:19'
labels:
  - frontend
  - bug
dependencies: []
priority: medium
type: bug
ordinal: 348000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner report: marking a position as applied leaves it selected in the multiple-choice list of job applications, and the document generation popup stays open.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Marking a job as applied removes it from the multi-selection
- [x] #2 If it was the only selected job, the generate-documents popup closes
- [x] #3 If other jobs remain selected, the popup stays open and shows only those jobs
- [x] #4 Covered by a test that drives the real board: one selected job and several selected jobs
<!-- AC:END -->
