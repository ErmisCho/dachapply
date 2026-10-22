---
id: TASK-336
title: A changed posting is re-analysed and its unreviewed documents redone
status: Done
assignee: []
created_date: '2026-10-22 06:43'
updated_date: '2026-10-22 11:18'
labels:
  - backend frontend
dependencies: []
priority: medium
ordinal: 336000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner 2026-10-22: run the pipeline for existing jobs too, with Profile settings. Measured on localhost: of 58 open jobs, 11 have a link and no analysis, 23 are apply/maybe (6 with nothing prepared or queued), 24 skip. Builds on TASK-324 (application_prep.start_pipeline/_pipeline, one run at a time, daily limit for new links). Owner chose: when a re-fetched ad changed, re-analyse the job; documents the owner has not reviewed are regenerated, reviewed/kept ones stay and get a 'posting changed' note. Today the automatic refresh (views.refresh_due_job_sources, TASK-269/311) stages or accepts changed text but does not re-analyse.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 When the automatic posting refresh accepts changed text for an open job, the job is re-analysed (commit) through the pipeline
- [x] #2 Documents not yet reviewed by the owner are regenerated after the re-analysis (apply/maybe); reviewed or kept documents are left untouched and the job shows 'Posting changed since these documents were made'
- [x] #3 A skip verdict after the change stops further document work but keeps existing files
- [x] #4 Counts against the daily analysis slider (TASK-335); Unlimited means no cap
- [x] #5 Tests cover changed vs unchanged text, reviewed vs unreviewed documents
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Merged #340 (with TASK-339 rules). Changed full postings of New/Reviewed jobs are accepted and re-analysed; To apply/Ready stage it and Use fetched re-analyses. 238 targeted tests (agent) / 142 re-run by coordinator.
<!-- SECTION:NOTES:END -->
