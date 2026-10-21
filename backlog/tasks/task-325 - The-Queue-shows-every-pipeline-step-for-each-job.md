---
id: TASK-325
title: The Queue shows every pipeline step for each job
status: To Do
assignee: []
created_date: '2026-10-21 06:59'
labels:
  - backend frontend
dependencies:
  - TASK-324
priority: high
ordinal: 325000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner 2026-10-21: one place to see where a job is, from link to documents. Today the Queue lists only documents (and blocked jobs). It also lists the TASK-324 stages read from prep['pipeline']: Fetching posting and Analysing fit as running items, a daily-limit wait as blocked, a skip verdict and a failed analysis as finished items. Read-only addition to queue_state plus PrepQueue.tsx; no migration.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A job whose prep['pipeline'].stage is fetching or analysing appears under Running with the stage name and no document label
- [ ] #2 A job held by the daily limit appears under Blocked with the reason and a working Retry
- [ ] #3 A skip verdict appears under Done as Not applying with its fit score; a failed analysis appears with its reason and Retry
- [ ] #4 Once documents are queued for the job, its pipeline row is replaced by the document rows (no duplicate)
- [ ] #5 Existing queue rows, actions and tests are unchanged
<!-- AC:END -->
