---
id: TASK-328
title: CV generator popup is compact and never goes under the navbar
status: In Progress
assignee: []
created_date: '2026-10-21 10:24'
updated_date: '2026-10-21 10:38'
labels:
  - frontend
dependencies: []
priority: medium
ordinal: 328000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner 2026-10-21 (screenshot of the board's Generate CV and Motivation Letter popup): 'the window should not be so big, like the current accepted text can be smaller to make the whole window minimalistic and elegant and this window should never go under the navbar in the top.' Measured in code: the compact popup is fixed top-3 inside the board's selection bar (its title rendered under the sticky .app-nav), has min-h 36rem, and its textareas grow to their content ([field-sizing:content], flex-auto), so a 4782-character accepted text stretches the window.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The popup's top edge is always below the navbar (any viewport size, scrolled or not) and it stays above the board content
- [x] #2 Current accepted text (and the other posting textareas) in the popup are a small fixed height that scrolls inside, resizable by the user, instead of growing to the full text
- [x] #3 The popup has no forced minimum height; it is only as tall as its content, capped to the space below the navbar
- [x] #4 The job page's full-size generator section is unchanged
- [ ] #5 Works at phone width with no horizontal scroll
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Merged in #322. Measured on localhost (1726x1634 viewport, job 1895): popup is portalled into body, top 45px vs navbar bottom 36.8px (also with the page scrolled 800px), height 537px (was nearly the viewport), Current accepted text 110px tall scrolling a 4782-char posting (scrollHeight 1328), popup centre hit-tests inside the dialog, no horizontal scroll. vitest 8 files 67 passed, tsc clean, CI green. Open: AC5 phone width -- the browser window could not be resized and the app refuses iframes, so it is checked in code only (width min(64rem,100vw-1.5rem), nav height measured).
<!-- SECTION:NOTES:END -->
