---
id: TASK-316
title: Board column order is saved to the account
status: In Progress
assignee: []
created_date: '2026-10-19 16:19'
updated_date: '2026-10-20 17:00'
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
- [ ] #3 Deployed via the owner's Azure deploy before localhost runs the new code
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-20 migration 0059 (board_column_order + reanalyse_late_text). Measured on a branch server with a scratch DB: browser order handed to an empty account once and the browser key removed; account order wins over a stale browser copy on reload; a fresh browser shows the account order; 'Move Skills left' saves to the account; PATCH with an unknown key -> 400. A backend test pins serializers.BOARD_COLUMNS to App.tsx columnOptions. AC3 waits for the Azure deploy.
<!-- SECTION:NOTES:END -->
