---
id: TASK-321
title: 'Profile setting: re-analyse when the real posting arrives late'
status: Done
assignee: []
created_date: '2026-10-19 18:45'
updated_date: '2026-10-22 13:44'
labels:
  - backend
  - frontend
dependencies: []
priority: low
ordinal: 321000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Follow-up to TASK-319: the owner wants to change the default later from the app. Needs a UserProfile field + migration, so it ships with the owner's next Azure deploy (with TASK-316).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Profile page toggle overrides DACHAPPLY_REANALYSE_LATE_TEXT for the account
- [x] #2 Shipped via the owner's Azure deploy before localhost runs it
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Verified 2026-10-22: Profile shows "Analyse a job again when its real posting arrives after a link-only analysis"; /api/profile/ reanalyse_late_text null = env default true.
<!-- SECTION:NOTES:END -->
