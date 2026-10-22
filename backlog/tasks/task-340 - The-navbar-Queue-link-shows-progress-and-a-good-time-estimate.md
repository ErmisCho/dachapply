---
id: TASK-340
title: The navbar Queue link shows progress and a good time estimate
status: Done
assignee: []
created_date: '2026-10-22 08:11'
updated_date: '2026-10-22 11:19'
labels:
  - backend frontend
dependencies: []
priority: medium
ordinal: 340000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner 2026-10-22, while today's daily batch ran (10 analyses + documents): 'the queue in the navbar might be better showing the progress and estimated amount of time needed (good estimation)'. Today the Queue page lists rows; only running document variants carry eta_seconds, queued items and pipeline stages (Waiting to analyse / Fetching posting / Analysing fit / Analysing requirements) have no estimate, and the navbar link shows nothing.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 While anything is running or queued, the navbar Queue link shows how much is left and the estimated time, e.g. 'Queue · 3 of 12 · ~25 min'; nothing extra when idle
- [x] #2 The estimate covers every pending item: analyses, requirements analyses and each queued document, using measured durations from past runs per kind (and per model for documents, reusing the existing CV timing history), not a fixed guess
- [x] #3 Hover/focus shows the breakdown (running item, analyses left, documents left) and the estimate updates as items finish
- [x] #4 Accuracy is checked live: the estimate at the start of a batch is compared with the actual finish time and reported
- [x] #5 Works at phone width; the navbar does not wrap worse than today
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Merged #342 and #346. Live: idle nav Queue; pending Queue 1/2 about 1 min with aria and hover breakdown; job 1533 re-analysis estimated 117 s (fallback, no history) vs actual 73.07 s recorded (+44 s); next estimate uses the measured median. Code review (10 findings) fixed; the old TASK-319 re-analysis now runs through the pipeline (visible, estimated, clears its reason).
<!-- SECTION:NOTES:END -->
