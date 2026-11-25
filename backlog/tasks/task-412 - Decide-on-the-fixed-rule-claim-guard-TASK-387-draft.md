---
id: TASK-412
title: Decide on the fixed-rule claim guard (TASK-387 draft)
status: Done
assignee: []
created_date: '2026-11-25 08:34'
updated_date: '2026-11-25 09:48'
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
- [x] #1 Measured: count of generated documents since 2026-11-19 containing a language level, certificate or tool not in the evidence
- [x] #2 Decision recorded: build on the draft branch, or close with the measured reason
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Measured 2026-11-25: the draft (branch draft/task-387-claim-guard) run over the 27 CVs and letters generated since 2026-11-19 (the owner's 6 base CVs counted as supported) flagged 0 unsupported certificates or language levels. A planted test showed gaps: it caught 'French C2' but missed 'Goethe-Zertifikat B2' and 'AWS-Certified'. Tool names were not measured (needs posting text). Decision (owner, 2026-11-25): close; the model self-review (TASK-385) stays the check. The draft branch is kept on GitHub.
<!-- SECTION:NOTES:END -->
