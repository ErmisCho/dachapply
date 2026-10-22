---
id: TASK-335
title: Daily sliders analyse waiting jobs and prepare documents for the best ones
status: Done
assignee: []
created_date: '2026-10-22 06:42'
updated_date: '2026-10-22 11:18'
labels:
  - backend frontend
dependencies: []
priority: high
ordinal: 335000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner 2026-10-22: run the pipeline for existing jobs too, with Profile settings. Measured on localhost: of 58 open jobs, 11 have a link and no analysis, 23 are apply/maybe (6 with nothing prepared or queued), 24 skip. Builds on TASK-324 (application_prep.start_pipeline/_pipeline, one run at a time, daily limit for new links). Owner: '10 with no analysis per day to be analyzed, 10 already that user has not applied and highest fit and priority, and have a slider ... granular ... unlimited'.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Profile has two sliders: 'Analyse waiting jobs per day' and 'Prepare documents per day', each 0 (off) .. 50 in steps of 1 plus Unlimited, default 10; stored on UserProfile (migration)
- [x] #2 Once a day while the local app runs, up to N open jobs (new/reviewed/to apply) with a link and no evaluation go through the TASK-324 pipeline, newest first
- [x] #3 Once a day, up to M open apply/maybe jobs with no prepared, queued or owner-generated documents get documents, highest fit then priority first
- [x] #4 The batches show in the Queue like other pipeline items and never run two analyses at once
- [x] #5 Tests cover selection, ordering, caps (0, N, Unlimited) and once-a-day behaviour
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Merged #340, deployed (Azure run 39742679519, migration 0061). Live: Profile shows the three sliders (10/10/7); right after the relaunch the daily run queued 10 analyses (9 waiting + 1 fetching).
<!-- SECTION:NOTES:END -->
