---
id: TASK-303
title: >-
  CV/letter generation speed, honest time estimates, and estimates in the model
  settings
status: Done
assignee: []
created_date: '2026-10-16 06:44'
updated_date: '2026-10-17 09:35'
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
- [x] #1 CV generation and automatic preparation default to GPT-6.1-Sol at high effort (configurable)
- [x] #2 Time estimates are learned per route, model, effort, speed and document mix; with no history for a model they say so instead of borrowing another model's time
- [x] #3 Every model/effort picker (CV generator, preparation, drafts, evaluate, settings) shows the expected duration for the chosen settings
- [x] #4 The GPT-6.1 revision failures are root-caused (with the specific validation reasons from #271) and fixed or reported with evidence
- [x] #5 Tests cover estimate grouping and fallback; a measured real CV run at the new default is recorded
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-16: #275 + #276. Default pick gpt-6.1-sol@high on localhost; pickers show learned or labelled rough estimates. Open: one measured real CV run at the new default (AC5).

AC5 measured 2026-10-16 15:00 UTC (cv-benchmarks.jsonl): 3 real generations at gpt-6.1-sol high/fast took 116.7, 127.2 and 130.1 s against an estimate of 118.8 s; a revision took 97.7 s.
<!-- SECTION:NOTES:END -->
