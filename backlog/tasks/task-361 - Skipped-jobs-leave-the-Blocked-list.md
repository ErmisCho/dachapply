---
id: TASK-361
title: Skipped jobs leave the Blocked list
status: To Do
assignee: []
created_date: '2026-11-06 18:30'
labels:
  - owner-request
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner: if a job listing was skipped or archived, it doesn't matter that the job was not fetched; delete it from the failed statuses. Measured: 5 of 10 Blocked rows are status new jobs the app recommends skipping, stuck on a failed re-analysis.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The Queue page's Blocked list leaves out a job that is Skipped or Archived, or that the app recommends skipping, whatever the reason it was blocked.
- [ ] #2 Such a job gets no further automatic retry, so it spends no model run.
- [ ] #3 If the recommendation changes to apply or maybe, a real blocked reason appears again.
- [ ] #4 Queue summary counts stay honest and no job, note or sidecar is deleted: rows are hidden, not destroyed.
<!-- AC:END -->
