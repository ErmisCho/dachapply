---
id: TASK-61.4
title: Display copyable paths for CV sources and generated artifacts
status: To Do
assignee: []
created_date: '2026-08-13 19:31'
labels:
  - cv-generation
  - ux
  - artifacts
dependencies: []
parent_task_id: TASK-61
priority: medium
ordinal: 66000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Always expose the filesystem paths involved in CV generation: the base CV template used and the generated CV and motivation-letter TeX/PDF files. Paths must be easy to select, copy with normal keyboard shortcuts, and open when the browser/platform permits.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Generation preview shows the selected base CV template path before generation starts
- [ ] #2 Ready and recompiled tasks show paths for every created CV and letter TeX/PDF artifact
- [ ] #3 Each path is rendered as selectable text with an explicit copy action and preserves standard keyboard selection/copy behavior
- [ ] #4 Each path has a clickable open action where the local browser/platform supports it, with a clear fallback when direct opening is blocked
- [ ] #5 Single-job and batch-generation views expose the same path information
- [ ] #6 Paths remain available after task polling completes and after a server restart when saved artifacts still exist
<!-- AC:END -->
