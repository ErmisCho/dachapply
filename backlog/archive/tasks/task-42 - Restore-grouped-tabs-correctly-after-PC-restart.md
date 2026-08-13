---
id: TASK-42
title: Restore grouped tabs correctly after PC restart
status: To Do
assignee: []
created_date: '2026-07-20 17:59'
updated_date: '2026-07-20 19:40'
labels: []
dependencies: []
ordinal: 43000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
After restarting the PC and reopening the desktop app, saved tabs can be replaced by tauri.localhost/blank.html pages or the last-open tabs are not restored across every tab group. Preserve and restore each group's actual tab state.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Restarting the PC and reopening the app restores the last-open tabs in every tab group
- [ ] #2 Restored tabs do not become tauri.localhost/blank.html pages unless that page was explicitly saved
- [ ] #3 A regression check covers persistence and restoration across multiple tab groups
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: @pi
created: 2026-07-20 19:40
---
Relocated to Chatgpt/TASK-91 because the Tauri source lives in that repository.
---
<!-- COMMENTS:END -->
