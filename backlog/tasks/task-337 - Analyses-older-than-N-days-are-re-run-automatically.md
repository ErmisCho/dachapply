---
id: TASK-337
title: Analyses older than N days are re-run automatically
status: To Do
assignee: []
created_date: '2026-10-22 06:43'
labels:
  - backend frontend
dependencies: []
priority: medium
ordinal: 337000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner 2026-10-22: run the pipeline for existing jobs too, with Profile settings. Measured on localhost: of 58 open jobs, 11 have a link and no analysis, 23 are apply/maybe (6 with nothing prepared or queued), 24 skip. Builds on TASK-324 (application_prep.start_pipeline/_pipeline, one run at a time, daily limit for new links). Owner chose: re-analyse open jobs whose latest analysis is older than N days (default 7, Profile slider with Off), e.g. after profile changes; same document rule as TASK-336.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Profile slider 'Re-analyse after N days': Off, 1..60, default 7 (migration)
- [ ] #2 Once a day, open jobs whose latest evaluation is older than N days are re-analysed, oldest first, within the daily analysis slider
- [ ] #3 Documents follow TASK-336's rule (unreviewed redone, reviewed kept with a note)
- [ ] #4 Tests cover the age cut-off, Off, and the shared daily cap
<!-- AC:END -->
