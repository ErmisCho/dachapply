---
id: TASK-307
title: 'Generate CV and Motivation Letter popup opens instantly, already loaded'
status: To Do
assignee: []
created_date: '2026-10-18 08:19'
labels:
  - frontend
dependencies: []
priority: medium
ordinal: 308000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner 2026-10-18: clicking Generate CV and Motivation Letter shows a loading state; it should already have loaded what it shows.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Everything the popup needs (templates, model options, generation preview/latest files) is fetched before the click (on job page load and on board-row hover/focus), so opening it renders its content immediately without a loading spinner when the data is fresh
- [ ] #2 Data still refreshes in the background after opening, so the popup never shows stale files after a generation
- [ ] #3 Measured in the browser on localhost: time from click to filled popup, before and after, with the network panel showing no blocking request on click
- [ ] #4 vitest covers the prefetch-then-instant-render path; tsc clean
<!-- AC:END -->
