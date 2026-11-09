---
id: TASK-356
title: Track database usage with alerts
status: Done
assignee: []
created_date: '2026-11-06 16:30'
labels:
  - owner-request
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner: track database usage with a notification on ermis.chorinopoulos@gmail.com every 5%, and show it on the local app. Chosen: both the localhost app list and a DACHApply panel, the panel only for that account.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Usage comes from Neon's API and never queries the database, so tracking cannot wake it or spend transfer, at most once an hour.
- [x] #2 A DACHApply panel shows transfer, compute and storage with used, limit and percent, only for the configured account; any other account gets nothing.
- [x] #3 The http://localhost app list shows the same usage.
- [x] #4 An email goes to the configured address at each 5% step of any metric, once per step per billing period, with no repeat after a restart.
- [x] #5 With no API key configured the app says so, sends no email and logs no errors, and the key never reaches a browser or log.
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Tests cover the 5% steps, restart, new period and the key never leaking. Checked live afterwards: the owner's key works on the Free plan, Neon's fields match, and the owner confirmed a real test email arrived. Storage read 0 on the new project at first.
<!-- SECTION:NOTES:END -->
