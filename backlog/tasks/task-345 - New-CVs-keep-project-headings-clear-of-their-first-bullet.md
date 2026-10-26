---
id: TASK-345
title: New CVs keep project headings clear of their first bullet
status: Done
assignee: []
created_date: '2026-10-25 15:38'
updated_date: '2026-10-26 10:53'
labels:
  - backend
dependencies: []
priority: medium
ordinal: 345000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found 2026-10-25 on a fresh MP Corporate Finance CV: underlined project names in Selected Projects touch their first bullet. The base CV v1.5 ends \resumeProjectHeading with \vspace{-7pt}; the base PDF shows the same. Owner chose: leave the base files alone, adjust newly generated CVs. Measured on a copy: \vspace{-2pt} clears it and keeps 2 pages.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A newly generated CV whose \resumeProjectHeading ends with \vspace{-7pt} gets \vspace{-2pt} instead; base files untouched; Adjust runs untouched
- [x] #2 Test covers the replacement and that other macros are not changed
- [x] #3 Live: next generated CV shows no heading/bullet contact
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Merged #362. Measured on a compiled copy of the MP Corporate Finance CV: -2pt removes the contact, 2 pages. Base files untouched. Open: AC3 on the next CV the app generates.

2026-10-26: AC3 verified on the first CV generated after the deploy (Eviden/Atos, 11:29): macro at -2pt, all three project headings clear of their first bullet, 2 pages.
<!-- SECTION:NOTES:END -->
