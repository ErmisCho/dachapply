---
id: TASK-303
title: >-
  CV/letter generation speed, honest time estimates, and estimates in the model
  settings
status: To Do
assignee: []
created_date: '2026-10-16 06:44'
labels: []
dependencies: []
ordinal: 304000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Measured 2026-10-16 (C:/latex/.dachapply-cache/cv-benchmarks.jsonl): GPT-6.1-Sol xhigh CV 357 s (estimate 83 s), letter 206 s (estimate 120 s); GPT-5.6-Sol xhigh CV 122 s. Revisions with GPT-6.1 medium failed twice. Owner decision: default for CVs and automatic preparation = GPT-6.1-Sol at high; show the expected duration wherever a model and its settings are chosen.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 CV generation and automatic preparation default to GPT-6.1-Sol at high effort (configurable)
- [ ] #2 Time estimates are learned per route, model, effort, speed and document mix; with no history for a model they say so instead of borrowing another model's time
- [ ] #3 Every model/effort picker (CV generator, preparation, drafts, evaluate, settings) shows the expected duration for the chosen settings
- [ ] #4 The GPT-6.1 revision failures are root-caused (with the specific validation reasons from #271) and fixed or reported with evidence
- [ ] #5 Tests cover estimate grouping and fallback; a measured real CV run at the new default is recorded
<!-- AC:END -->
