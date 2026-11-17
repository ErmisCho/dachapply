---
id: TASK-382
title: 'Parse inline OLD:/NEW: blocks without AI'
status: Done
assignee: []
created_date: '2026-11-17 07:59'
updated_date: '2026-11-17 08:20'
labels: []
dependencies: []
priority: medium
ordinal: 383000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Adjust with 'OLD: Vienna, 16 November 2026' / 'NEW: Vienna, \today' (marker and text on one line) skipped the exact no-AI route because exact_revision_plan only accepts a marker alone on its line; it fell to gemma3:4b, whose unescaped \t was refused by the gate, then to the cloud model (adjustments.jsonl 2026-11-17T08:58).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 exact_revision_plan accepts 'OLD: <text>' and 'NEW: <text>' on the marker line, alone or continued on following lines
- [x] #2 The 2026-11-17 date request routes 'exact' on the real DeepJudge letter (dry run, no write)
- [x] #3 Existing own-line OLD:/NEW: behaviour and tests unchanged; a new test fails on the old code and passes on the fix
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Fix merged in #421 (c57c02b). Red/green: new test fails on old parser. Dry run of the logged instruction on a copy of the real DeepJudge letter: exact route, byte-identical to the cloud result. CI green; local suite 2259 pass, 1 unrelated flake (test_analysis_lanes, passes alone). Localhost runtime still at 7640567 until the owner restarts it from the dashboard.
<!-- SECTION:NOTES:END -->
