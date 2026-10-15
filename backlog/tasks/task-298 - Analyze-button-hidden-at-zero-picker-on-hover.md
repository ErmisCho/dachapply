---
id: TASK-298
title: 'Analyze button: hidden at zero, picker on hover'
status: To Do
assignee: []
created_date: '2026-10-15 09:10'
labels: []
dependencies: []
ordinal: 299000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner (2026-10-15): 'Analyze N new jobs' and the small picker button next to it in the navbar should only show when there are new jobs to analyze; on desktop the picker's function (analyze one chosen job) should open from hovering the Analyze button instead of a separate button. Phone (no hover) keeps a tap-friendly path in the menu.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 With 0 new jobs neither the Analyze button nor the picker is shown (desktop navbar and phone menu)
- [ ] #2 On desktop the separate picker button is gone; hovering (and keyboard-focusing) Analyze N new jobs opens the one-job list; clicking the button still analyzes all N
- [ ] #3 On touch/phone the one-job choice stays reachable without hover
- [ ] #4 Verified in the browser; vitest and tsc pass; tests fail when the zero-hide or hover-open logic is removed
<!-- AC:END -->
