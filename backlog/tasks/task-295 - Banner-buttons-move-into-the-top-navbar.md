---
id: TASK-295
title: Banner buttons move into the top navbar
status: In Progress
assignee: []
created_date: '2026-10-14 09:02'
updated_date: '2026-10-14 12:48'
labels: []
dependencies: []
ordinal: 296000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner (2026-10-14): 'Analyze X new jobs', 'Add job' and the other buttons of the 'Job command center' bar belong in the top navbar; the bar itself then goes.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Analyze X new jobs (with its count), Add job and the other bar buttons are in the top navbar on desktop and in the phone menu
- [x] #2 The Job command center bar is removed from the board
- [x] #3 Buttons keep their behaviour (verified by clicking each in the browser); vitest and tsc pass
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-14: #251. Localhost desktop: Analyze N new jobs and + Add job in the navbar (Add job -> /add), bar gone, no horizontal overflow. Open: phone menu (owner).
<!-- SECTION:NOTES:END -->
