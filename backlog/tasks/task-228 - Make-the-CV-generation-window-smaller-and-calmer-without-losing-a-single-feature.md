---
id: TASK-228
title: >-
  Make the CV generation window smaller and calmer without losing a single
  feature
status: To Do
assignee: []
created_date: '2026-09-10 11:49'
labels:
  - frontend
dependencies:
  - TASK-227
priority: medium
ordinal: 227000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner request, 2026-09-10: make the CV generation window minimalistic and smaller but concise, without removing any features.

The popup is App.tsx line 587 - one 11,162-character line. Its shell is fixed at `h-[80vh] w-[44rem] max-w-[calc(100vw-2rem)] overflow-y-auto`, so it is 704px wide and 80% of the viewport tall whether it is showing four dropdowns or a full generation report, and it scrolls internally rather than fitting.

Everything currently in it, so the "without removing any features" half is checkable rather than a promise: Provider, Model, Effort, Speed, Detected language, Create CV, Create motivation letter, Adjust latest generated files, Copy generated TeX files, the generation report (Main changes, Changed files, Checks, Not claimed), Close - plus whatever TASK-227 adds, which is why this depends on it.

Smaller and calmer are different things and both are wanted: fewer pixels, and less shouting inside them. Progressive disclosure (the report and the advanced model controls are not needed until they are) is the obvious lever, but collapsing a control is only acceptable if it is still reachable - hiding is not removing, and removing is out of scope.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Every control listed in the description is still reachable after the change, checked off one at a time against the running window rather than asserted as a group
- [ ] #2 The window is measurably smaller: rendered width and height in pixels are stated before and after, for the same job in the same state
- [ ] #3 The common case - opening the window to generate, before any report exists - needs no inner scrolling, or the scrolling that remains is named and justified
- [ ] #4 It still works at 360px and 430px wide, verified by a stated measurement method rather than by reading the CSS
- [ ] #5 Frontend tests cover anything newly collapsible staying reachable, and the result is verified in the served bundle at localhost:8000 after `cd frontend && npm run build`
<!-- AC:END -->
