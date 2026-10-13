---
id: TASK-283
title: 'Board list: stop sending every job''s full posting text (575 KB, ~1.1 s)'
status: To Do
assignee: []
created_date: '2026-10-13 10:50'
labels:
  - performance
dependencies: []
ordinal: 281000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Measured 2026-10-13 against Neon (TASK-282 follow-up): GET /api/jobs/?...&board=1 returns 575 KB for 111 jobs and takes ~1.1 s, while query count is only 5; the New-only board (63 KB) takes 348 ms. Cost scales with payload: full original_source_text/raw_description and other long text per job. The board rows only need summary fields; the job page loads the detail endpoint.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Board list response for the owner's 111 jobs is under 100 KB and its median (20 warm requests, localhost) is under 200 ms
- [ ] #2 The board renders and behaves exactly as before (search, filters, badges, sorting, section headers, copy/export actions) - verified in the browser
- [ ] #3 Any board feature that needs a long text field gets it from the detail endpoint or a dedicated field, not the list
- [ ] #4 Query counts stay pinned (TASK-282 tests) and the full backend suite, frontend tests and tsc pass
<!-- AC:END -->
