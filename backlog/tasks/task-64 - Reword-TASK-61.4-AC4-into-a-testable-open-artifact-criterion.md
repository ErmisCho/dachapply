---
id: TASK-64
title: Reword TASK-61.4 AC4 into a testable open-artifact criterion
status: Done
assignee:
  - '@claude'
created_date: '2026-08-13 21:44'
updated_date: '2026-08-14 17:05'
labels:
  - chore
  - cv-generation
dependencies: []
priority: low
ordinal: 69000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
TASK-61.4 AC4 reads 'Each path has a clickable open action where the local browser/platform supports it, with a clear fallback when direct opening is blocked'. This has no testable threshold - 'where the platform supports it' cannot be graded pass or fail - so the criterion was deliberately left unimplemented during the TASK-61 session. It is also the one part of the path-visibility feature with real security downside: the security review confirmed no arbitrary-path opener exists today, and any open affordance must stay restricted to artifacts already present in the task payload. Decide the intended behaviour and restate it as something verifiable.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 AC4 is restated with a concrete, verifiable expectation
- [x] #2 The restated criterion keeps the open action limited to artifacts present in the task payload, never an arbitrary path
<!-- AC:END -->
