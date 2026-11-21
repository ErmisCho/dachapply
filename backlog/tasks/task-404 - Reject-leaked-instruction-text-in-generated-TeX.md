---
id: TASK-404
title: Reject leaked instruction text in generated TeX
status: To Do
assignee: []
created_date: '2026-11-21 09:16'
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
- [ ] #1 Validation rejects generated TeX containing instruction markers (OLD:, NEW:, FINAL VALIDATION, CHANGE n) outside comments, triggering the existing repair attempt (test)
- [ ] #2 Normal documents are not rejected (test with a real template)
<!-- AC:END -->
