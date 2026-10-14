---
id: TASK-296
title: Auto-link mail only for jobs that reached an interview
status: In Progress
assignee: []
created_date: '2026-10-14 20:32'
labels: []
dependencies: []
ordinal: 297000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner (2026-10-14): mail should only be tracked/auto-linked for jobs that reached at least one interview stage and did not go back to applied or new; no need to map every job listing. Applies to the live auto-attach in the mailbox check and to the Re-check unmatched mail dry run/apply (TASK-291). Manual attach stays available for any job.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Auto-attach (live check and re-check) only targets jobs that reached an interview (same rule as the funnel's 'reached interview') and whose current status is not new, reviewed, to_apply or applied
- [ ] #2 Mail for other jobs stays unmatched and can still be attached by hand
- [ ] #3 The re-check dry run on the owner's data lists only mail for qualifying jobs
- [ ] #4 Tests cover qualifying, never-interviewed and back-to-applied jobs; each fails when its logic is removed
<!-- AC:END -->
