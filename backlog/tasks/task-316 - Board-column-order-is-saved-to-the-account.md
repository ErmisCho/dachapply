---
id: TASK-316
title: Board column order is saved to the account
status: To Do
assignee: []
created_date: '2026-10-19 16:19'
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
- [ ] #1 UserProfile stores the column order (migration), exposed via /profile/ like board_status_order, validated against the known column keys
- [ ] #2 The board uses the account order on every browser; an existing browser-only order is migrated to the account once
- [ ] #3 Deployed via the owner's Azure deploy before localhost runs the new code
<!-- AC:END -->
