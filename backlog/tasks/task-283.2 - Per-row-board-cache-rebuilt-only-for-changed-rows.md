---
id: TASK-283.2
title: Per-row board cache rebuilt only for changed rows
status: In Progress
assignee: []
created_date: '2026-10-13 14:23'
updated_date: '2026-10-14 06:15'
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
- [x] #1 Board list (all 111 jobs) median TTFB under 200 ms on localhost against Neon, 20 warm requests
- [ ] #2 Board list on Azure median under 200 ms, 20 warm requests
- [x] #3 Response is byte-identical to the uncached response for the same data (hash compare on the owner's board)
- [x] #4 Changing any field the board shows - job, evaluation, note, mailbox match, submitted-for - updates that row on the next load; one test per source, each fails if the stamp ignores that source
- [x] #5 A guard test fails if a new field is added to the board list serializers without the stamp covering it
- [x] #6 Rows are never served across accounts (cache key includes the viewer)
- [x] #7 Full backend suite, vitest and tsc pass
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-13: serialized board rows cached per (viewer, job) in a process-local LocMem alias (board_rows, all runtimes incl. Azure). A warm load runs one stamp query (ids + version stamp built in SQL from BOARD_ROW_SOURCES) and only fetches/serializes rows whose stamp changed. No invalidation needed: every request reads stamps from the DB. Writes that skip updated_at are covered by stamping those columns; two update_fields saves now include updated_at. 16 new tests, each falsified; byte-identical on vs off. Local board_list 2 -> 1 query warm. AC#1/#2 (timings on Neon/Azure) to be measured after deploy.

2026-10-14: localhost median TTFB 150 ms (113 jobs, 20 warm). Uncached first request and cached ones hash identically (18fd751e5fa3e9). AC#2 needs an Azure deploy.
<!-- SECTION:NOTES:END -->
