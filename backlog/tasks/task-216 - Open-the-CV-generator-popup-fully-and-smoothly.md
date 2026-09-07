---
id: TASK-216
title: Open the CV generator popup fully and smoothly
status: Done
assignee:
  - '@pi'
created_date: '2026-09-02 09:00'
updated_date: '2026-09-07 13:37'
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
Closed 2026-09-07 after independent coordinator verification (TW-003/TW-004), not on the implementer's report.

Re-measured in Chrome against the running app (main-runtime at e144e4e, Vite 5173 via the 8000 redirect) with GET /api/jobs/{id}/cv-generation/ shimmed to resolve 6s late:
- mount at 68.1ms, dialog 704x1312 at (225.14, 329)
- 41 bounding-box samples over 10.0s: max delta dx 0, dy 0, dw 0, dh 0; one distinct size throughout
- operability exercised, not just observed: focus lands inside the dialog, Close button closes it, reopen works, Escape closes it

Gate re-run on current main: 1054 backend tests, 207 frontend tests / 12 files, tsc --noEmit clean, production build exit 0.

Asian Dad: PERFECT, all 5 sealed criteria PASS (self-graded disclosure stands).

Caveat recorded for future readers: frontend/src/cvPopup.test.tsx asserts the literal class h-[80vh] in static SSR markup. That pins a class name, not a rendered box - it would stay green if the popup grew on load. Criteria 1, 2 and 5 are carried by the browser measurement above, not by that test.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Stabilized the single-job CV generator popup at its existing 80vh viewport size, exposed loading and Close controls before preview discovery, and reused the app's dialog focus/Escape behavior. Verified with a synthetic delayed browser measurement (38.3ms initial mount, 0px geometry shift), 207 frontend tests, production build, and 1054 backend tests.
<!-- SECTION:FINAL_SUMMARY:END -->
