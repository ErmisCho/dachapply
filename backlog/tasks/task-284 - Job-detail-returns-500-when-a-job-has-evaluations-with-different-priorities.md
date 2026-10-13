---
id: TASK-284
title: Job detail returns 500 when a job has evaluations with different priorities
status: To Do
assignee: []
created_date: '2026-10-13 10:50'
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
- [ ] #1 A job with 2+ evaluations of different priorities returns 200 on /api/jobs/<id>/ and appears exactly once on the board
- [ ] #2 The annotation uses the latest evaluation's priority (same rule as the fit score) - a test pins it
- [ ] #3 Query counts stay pinned and the full backend suite passes
<!-- AC:END -->
