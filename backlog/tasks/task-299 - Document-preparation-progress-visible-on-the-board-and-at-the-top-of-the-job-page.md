---
id: TASK-299
title: >-
  Document preparation progress visible on the board and at the top of the job
  page
status: Done
assignee: []
created_date: '2026-10-15 11:32'
updated_date: '2026-10-18 09:00'
labels: []
dependencies: []
ordinal: 300000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner (2026-10-15), watching Wienerberger prepare: the progress should be visible. Owner chose: a compact badge on the job's board row (e.g. 'Preparing 2 docs · 45%', then ready/failed) and the 'Prepared documents' panel at the top of the job page.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A job with running preparation shows a compact progress badge on its board row that updates while running and turns into ready / failed when done
- [x] #2 The board badge does not go stale through the per-row board cache (TASK-283.2) and costs no extra per-row file reads on the board request
- [x] #3 The Prepared documents panel sits at the top of the job page
- [x] #4 Verified in the browser while a real preparation runs; vitest, tsc and backend suite pass
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-16: #272. Panel at top verified on Wienerberger while running (earlier version); board badge needs the next running preparation to check in the browser.

Verified 2026-10-18 on PORR 1544: board row showed 'Preparing 1 doc ▓░░░░ 22% · ~2 min left' while cv-de ran, then '1 doc ready'.
<!-- SECTION:NOTES:END -->
