---
id: TASK-412
title: Decide on the fixed-rule claim guard (TASK-387 draft)
status: To Do
assignee: []
created_date: '2026-11-25 08:34'
labels: []
dependencies: []
priority: low
ordinal: 416000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
TASK-387 was archived on 2026-11-19 when the model self-review (TASK-385) shipped. An unfinished fixed-rule draft exists on branch draft/task-387-claim-guard (claim_guard.py plus test, about 70 lines): it flags language levels, certificates and tools in generated TeX that the candidate evidence does not support. Decide whether to finish it as a check on top of the self-review, measuring first how often the self-review misses such claims in adjustments.jsonl.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Measured: count of generated documents since 2026-11-19 containing a language level, certificate or tool not in the evidence
- [ ] #2 Decision recorded: build on the draft branch, or close with the measured reason
<!-- AC:END -->
