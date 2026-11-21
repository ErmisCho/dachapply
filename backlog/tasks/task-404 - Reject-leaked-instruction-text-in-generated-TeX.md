---
id: TASK-404
title: Reject leaked instruction text in generated TeX
status: Done
assignee: []
created_date: '2026-11-21 09:16'
updated_date: '2026-11-21 09:45'
labels: []
dependencies: []
priority: high
ordinal: 405000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Prompt/instruction text (OLD:, NEW:, FINAL VALIDATION) leaked into generated .tex 8 times. Evidence: audits 2026-11-20 (jobs/6526c3ef/tmp audit-reliability.md, audit-intake.md, audit-quality.md). Owner approved 2026-11-21.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Validation rejects generated TeX containing instruction markers (OLD:, NEW:, FINAL VALIDATION, CHANGE n) outside comments, triggering the existing repair attempt (test)
- [x] #2 Normal documents are not rejected (test with a real template)
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
PR #439. Running on localhost 2026-11-21 (runtime 03b8d2d, health 200; code presence checked). No real template trips the guard (v1.6 CVs + 4 letter templates checked).
<!-- SECTION:NOTES:END -->
