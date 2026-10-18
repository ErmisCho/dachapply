---
id: TASK-310
title: Ready to submit only for jobs worth applying to
status: Done
assignee: []
created_date: '2026-10-18 22:36'
updated_date: '2026-10-18 23:18'
labels: []
dependencies: []
ordinal: 311000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner (2026-10-19): Ready to submit held 13 jobs, 4 of them recommended 'skip'. Generating documents promotes any unapplied job, whatever its evaluation says.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Finished document generation (cv_tasks.mark_ready_to_submit and every caller, incl. the mark_ready_to_submit command) does not promote a job whose latest evaluation recommends 'skip'; 'apply', 'maybe' and jobs without an evaluation are promoted as before
- [x] #2 The status of an already-promoted job is never changed by this (no data migration)
- [x] #3 A test fails when the skip check is removed
- [x] #4 Backend suite passes
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-19: #294. Explicit final-package selection still promotes (respect_skip=False). Suite green in CI.
<!-- SECTION:NOTES:END -->
