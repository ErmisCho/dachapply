---
id: TASK-345
title: New CVs keep project headings clear of their first bullet
status: To Do
assignee: []
created_date: '2026-10-25 15:38'
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
- [ ] #1 A newly generated CV whose \resumeProjectHeading ends with \vspace{-7pt} gets \vspace{-2pt} instead; base files untouched; Adjust runs untouched
- [ ] #2 Test covers the replacement and that other macros are not changed
- [ ] #3 Live: next generated CV shows no heading/bullet contact
<!-- AC:END -->
