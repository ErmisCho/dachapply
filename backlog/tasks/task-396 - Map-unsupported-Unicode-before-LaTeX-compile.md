---
id: TASK-396
title: Map unsupported Unicode before LaTeX compile
status: To Do
assignee: []
created_date: '2026-11-21 09:15'
labels: []
dependencies: []
priority: high
ordinal: 397000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Exact edits failed on characters like U+2264 (Unicode character not set up for use with LaTeX). Evidence: audits 2026-11-20 (jobs/6526c3ef/tmp audit-reliability.md, audit-intake.md, audit-quality.md). Owner approved 2026-11-21.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Before compiling, characters known to break the templates (at least ≤ ≥ → – — non-breaking space where unsupported) are mapped to LaTeX equivalents; a test compiles/validates text containing U+2264 without the Unicode error
- [ ] #2 Text that already compiles is byte-identical after mapping
<!-- AC:END -->
