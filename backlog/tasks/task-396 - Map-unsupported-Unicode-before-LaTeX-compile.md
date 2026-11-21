---
id: TASK-396
title: Map unsupported Unicode before LaTeX compile
status: Done
assignee: []
created_date: '2026-11-21 09:15'
updated_date: '2026-11-21 09:45'
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
- [x] #1 Before compiling, characters known to break the templates (at least ≤ ≥ → – — non-breaking space where unsupported) are mapped to LaTeX equivalents; a test compiles/validates text containing U+2264 without the Unicode error
- [x] #2 Text that already compiles is byte-identical after mapping
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
PR #438. Running on localhost 2026-11-21 (runtime 03b8d2d, health 200; code presence checked). Real pdflatex on the v1.6 base CV: unmapped U+2264 fails, mapped compiles; untouched text byte-identical.
<!-- SECTION:NOTES:END -->
