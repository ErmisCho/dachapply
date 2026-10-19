---
id: TASK-321
title: 'Profile setting: re-analyse when the real posting arrives late'
status: To Do
assignee: []
created_date: '2026-10-19 18:45'
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
- [ ] #1 Profile page toggle overrides DACHAPPLY_REANALYSE_LATE_TEXT for the account
- [ ] #2 Shipped via the owner's Azure deploy before localhost runs it
<!-- AC:END -->
