---
id: TASK-382
title: 'Parse inline OLD:/NEW: blocks without AI'
status: To Do
assignee: []
created_date: '2026-11-17 07:59'
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
- [ ] #1 exact_revision_plan accepts 'OLD: <text>' and 'NEW: <text>' on the marker line, alone or continued on following lines
- [ ] #2 The 2026-11-17 date request routes 'exact' on the real DeepJudge letter (dry run, no write)
- [ ] #3 Existing own-line OLD:/NEW: behaviour and tests unchanged; a new test fails on the old code and passes on the fix
<!-- AC:END -->
