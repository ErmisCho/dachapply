---
id: TASK-328
title: CV generator popup is compact and never goes under the navbar
status: To Do
assignee: []
created_date: '2026-10-21 10:24'
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
- [ ] #1 The popup's top edge is always below the navbar (any viewport size, scrolled or not) and it stays above the board content
- [ ] #2 Current accepted text (and the other posting textareas) in the popup are a small fixed height that scrolls inside, resizable by the user, instead of growing to the full text
- [ ] #3 The popup has no forced minimum height; it is only as tall as its content, capped to the space below the navbar
- [ ] #4 The job page's full-size generator section is unchanged
- [ ] #5 Works at phone width with no horizontal scroll
<!-- AC:END -->
