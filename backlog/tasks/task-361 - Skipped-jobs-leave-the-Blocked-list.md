---
id: TASK-361
title: Skipped jobs leave the Blocked list
status: Done
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
- [x] #1 The Queue page's Blocked list leaves out a job that is Skipped or Archived, or that the app recommends skipping, whatever the reason it was blocked.
- [x] #2 Such a job gets no further automatic retry, so it spends no model run.
- [x] #3 If the recommendation changes to apply or maybe, a real blocked reason appears again.
- [x] #4 Queue summary counts stay honest and no job, note or sidecar is deleted: rows are hidden, not destroyed.
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-10: merged #377 (Codex review found and fixed a stranded over-budget Use fetched; regression test shown failing without the fix). CI full suite green; deployed in 64812d1, localhost updated.
<!-- SECTION:NOTES:END -->
