---
id: TASK-216
title: Open the CV generator popup fully and smoothly
status: In Progress
assignee:
  - '@pi'
created_date: '2026-09-02 09:00'
updated_date: '2026-09-02 14:20'
labels:
  - frontend
  - bug
dependencies: []
modified_files:
  - frontend/src/App.tsx
  - frontend/src/cvPopup.test.tsx
  - .orchestrator/debug/task-216-2026-09-02-bugfix-1-1.md
  - .orchestrator/debug/task-216-2026-09-02-bugfix-1-2.md
  - .claude/.asian-dad/task-216-cv-popup-smooth-open-rubric.json
  - backlog/tasks/task-216 - Open-the-CV-generator-popup-fully-and-smoothly.md
ordinal: 215000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Clicking Generate CV and Motivation Letter currently mounts a partially populated popup immediately, then expands or shifts after provider discovery finishes several seconds later. Open a stable complete popup immediately, with slow preview/provider data loading inside it without changing the window geometry.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The CV generator popup reaches its final size and position on the initial render
- [x] #2 Slow preview/provider discovery does not resize or reposition the popup
- [x] #3 The popup shows an immediate in-place loading state until controls are ready
- [x] #4 Keyboard and button access remain usable and accessible
- [x] #5 Frontend regression tests and production build pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Stabilize only the compact CvGenerator shell at its existing 80vh cap while keeping the detail-page generator unchanged. 2. Reuse Loading and useDismiss so loading, Close, focus, and Escape work before preview discovery finishes. 3. Add one DOM-less initial-shell regression. 4. Measure delayed preview geometry in Chrome, run frontend tests/build and the configured backend suite, then evaluate, commit, push, squash-merge, verify release runtime, and close.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Root cause reproduced in synthetic Chrome with a delayed preview: the compact popup grew from 81.28px to 1028.60px (+947.32px) because max-height reserved no space while preview-gated controls were absent. Implemented a fixed compact shell, immediate loading/close affordances, and existing focus/Escape behavior. Initial focused test was blocked because the new worktree had no node_modules; debug artifact 1-2 records the setup failure before npm ci.

Verification passed: MutationObserver saw the complete 704x1168.86px compact shell mount in 38.3ms; synthetic 6-second preview discovery produced 0px x/y/width/height shift; dialog focus, Escape, Close, and trigger-focus restoration passed in Chrome. Frontend: 12 files / 207 tests passed and production build passed. Backend: 1054 tests passed. npm ci audit found 0 vulnerabilities. Asian Dad verdict: PERFECT (self-graded disclosure).
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Stabilized the single-job CV generator popup at its existing 80vh viewport size, exposed loading and Close controls before preview discovery, and reused the app's dialog focus/Escape behavior. Verified with a synthetic delayed browser measurement (38.3ms initial mount, 0px geometry shift), 207 frontend tests, production build, and 1054 backend tests.
<!-- SECTION:FINAL_SUMMARY:END -->
