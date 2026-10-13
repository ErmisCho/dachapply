---
id: TASK-283.2
title: Per-row board cache rebuilt only for changed rows
status: To Do
assignee: []
created_date: '2026-10-13 14:23'
labels:
  - performance
dependencies:
  - TASK-283.1
parent_task_id: TASK-283
ordinal: 284000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Keep each job's serialized board row in a server cache with a version stamp derived from the data (job, latest evaluation, general notes, mailbox matches). A board load reads ids + stamps in one cheap query and serializes only rows whose stamp changed.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Board list (all 111 jobs) median TTFB under 200 ms on localhost against Neon, 20 warm requests
- [ ] #2 Board list on Azure median under 200 ms, 20 warm requests
- [ ] #3 Response is byte-identical to the uncached response for the same data (hash compare on the owner's board)
- [ ] #4 Changing any field the board shows - job, evaluation, note, mailbox match, submitted-for - updates that row on the next load; one test per source, each fails if the stamp ignores that source
- [ ] #5 A guard test fails if a new field is added to the board list serializers without the stamp covering it
- [ ] #6 Rows are never served across accounts (cache key includes the viewer)
- [ ] #7 Full backend suite, vitest and tsc pass
<!-- AC:END -->
