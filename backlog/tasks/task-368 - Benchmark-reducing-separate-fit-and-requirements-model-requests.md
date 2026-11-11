---
id: TASK-368
title: Benchmark reducing separate fit and requirements model requests
status: To Do
assignee: []
created_date: '2026-11-11 15:24'
labels:
  - pipeline
  - performance
dependencies: []
priority: medium
type: spike
ordinal: 368000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Grounded opportunity from Backlog doc-1, Application pipeline efficiency opportunities - 2026-11-11. Historical timings are not a controlled speedup comparison. Preserve TASK-348 all-letter alternatives, TASK-303 model quality/defaults, owner data, cancellation, per-account access and daily budgets. For apply/maybe jobs with missing requirements, automatic fit evaluation and requirements extraction can call a model separately on the same posting. Existing combined import concepts may help, but combining requests can change latency and answer quality. Establish whether one request can replace two safely before changing defaults.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A matched representative posting set compares the current separate path and a combined candidate, recording provider requests, elapsed time, failures and output-quality differences with identical model settings.
- [ ] #2 Compare fit verdicts and source-grounded application requirements, including missing/ambiguous postings, explicit language, required/unwanted letters and skip decisions; parser/schema validity alone is not the quality bar.
- [ ] #3 Owner-edited requirements, late posting updates, failure isolation, cancellation and strict import validation remain authoritative.
- [ ] #4 No request is repeated just because valid requirements are already stored; retained or rejected combinations are documented with measured evidence, not a promised percentage saving.
- [ ] #5 Do not change the current production default unless the measured benefit and labelled quality comparison support it; any approved change leaves regression coverage.
<!-- AC:END -->
