---
id: TASK-61
title: >-
  Improve CV generation controls, feedback, revision speed, and artifact
  visibility
status: In Progress
assignee:
  - '@claude'
created_date: '2026-08-13 19:30'
updated_date: '2026-08-13 20:01'
labels:
  - cv-generation
  - ux
  - performance
dependencies: []
priority: high
ordinal: 62000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Track the remaining CV-generation usability and performance problems: provider/model capability controls, transparent phase progress, instruction-faithful fast revisions, realistic time estimates, and visible filesystem paths for source and generated artifacts.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Each reported concern is covered by a focused child task with testable acceptance criteria
- [x] #2 The child tasks can be delivered independently without losing the shared CV-generation context
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
AC1 was only genuinely true from 2026-08-14. Until then TASK-61.4 AC4 ('a clickable open action where the local browser/platform supports it') had no testable threshold and was the documented counterexample to this criterion; TASK-64 restated it as a closed-key Reveal endpoint, which is binary-checkable, and it is now implemented. AC2 held throughout: 61.1-61.4 were each delivered and verified on their own.

STATUS stays In Progress deliberately even though both ACs are met. This is a parent tracker, and two children still have open criteria that only a live provider run can close:
- TASK-61.2 AC6 - one real generation, then confirm cv-benchmarks.jsonl holds an estimated-vs-actual row.
- TASK-61.3 AC5 - one real revision, passes if that row's actual_seconds < 30.
Done children: 61.1, 61.4. Spun out and closed: TASK-62 (test isolation), TASK-63 (artifact-path rehydration), TASK-64 (AC4 rewording).
<!-- SECTION:NOTES:END -->
