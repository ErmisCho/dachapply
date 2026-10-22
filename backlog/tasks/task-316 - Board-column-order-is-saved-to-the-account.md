---
id: TASK-316
title: Board column order is saved to the account
status: Done
assignee: []
created_date: '2026-10-19 16:19'
updated_date: '2026-10-22 13:44'
labels:
  - backend
  - frontend
dependencies: []
priority: low
ordinal: 316000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Follow-up to TASK-315 (owner chose browser-only now, account later). Needs a UserProfile field + migration, so it ships with the owner's next Azure deploy; localhost shares the Neon DB and breaks if code runs ahead of the schema.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 UserProfile stores the column order (migration), exposed via /profile/ like board_status_order, validated against the known column keys
- [x] #2 The board uses the account order on every browser; an existing browser-only order is migrated to the account once
- [x] #3 Deployed via the owner's Azure deploy before localhost runs the new code
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Verified 2026-10-22 on localhost after the deploy: /api/auth/me/ returns board_column_order from the account (11 keys); migration 0059 deployed.
<!-- SECTION:NOTES:END -->
