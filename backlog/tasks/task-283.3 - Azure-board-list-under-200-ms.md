---
id: TASK-283.3
title: Azure board list under 200 ms
status: In Progress
assignee: []
created_date: '2026-10-14 07:05'
labels: []
dependencies: []
parent_task_id: TASK-283
ordinal: 286000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
After TASK-283.2 the deployed board list takes a median 217 ms (111 jobs, 20 warm requests) vs 150 ms on localhost; /api/health/ alone is 89 ms. Step 1: a Server-Timing header (total, db time, query count) to see where the ~130 ms go. Step 2: cut the biggest part.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Deployed responses carry Server-Timing with total, db time and query count for logged-in users
- [ ] #2 Azure board list median under 200 ms over 20 warm requests
<!-- AC:END -->
