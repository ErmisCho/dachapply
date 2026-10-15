---
id: TASK-298
title: 'Analyze button: hidden at zero, picker on hover'
status: Done
assignee: []
created_date: '2026-10-15 09:10'
updated_date: '2026-10-15 10:40'
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
- [x] #1 With 0 new jobs neither the Analyze button nor the picker is shown (desktop navbar and phone menu)
- [x] #2 On desktop the separate picker button is gone; hovering (and keyboard-focusing) Analyze N new jobs opens the one-job list; clicking the button still analyzes all N
- [x] #3 On touch/phone the one-job choice stays reachable without hover
- [x] #4 Verified in the browser; vitest and tsc pass; tests fail when the zero-hide or hover-open logic is removed
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-15: #262. Localhost with 0 new jobs: only '+ Add job' in the navbar. Hover list not seen in the browser yet (needs new jobs).

2026-10-15: with 2 simulated new jobs (browser-only), hovering Analyze 2 new jobs opened 'Analyze one new job' with both; no separate picker button; at 0 jobs nothing shows.
<!-- SECTION:NOTES:END -->
