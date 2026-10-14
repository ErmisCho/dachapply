---
id: TASK-284
title: Job detail returns 500 when a job has evaluations with different priorities
status: Done
assignee: []
created_date: '2026-10-13 10:50'
updated_date: '2026-10-14 12:48'
labels:
  - bug
dependencies: []
ordinal: 282000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found by the TASK-282 agent (reproduced on the original code): the priority_rank annotation joins evaluations, so distinct() yields one row per priority and /api/jobs/<id>/ raises MultipleObjectsReturned; the board list likely duplicates that job's row too.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A job with 2+ evaluations of different priorities returns 200 on /api/jobs/<id>/ and appears exactly once on the board
- [x] #2 The annotation uses the latest evaluation's priority (same rule as the fit score) - a test pins it
- [x] #3 Query counts stay pinned and the full backend suite passes
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-14: #253. priority_rank and fit sort from the latest evaluation; localhost: 111 board rows, 0 duplicates, all 111 detail pages 200.
<!-- SECTION:NOTES:END -->
