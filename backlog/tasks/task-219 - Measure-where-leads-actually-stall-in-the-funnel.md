---
id: TASK-219
title: Measure where leads actually stall in the funnel
status: Done
assignee: []
created_date: '2026-09-08 11:03'
labels:
  - backend
  - frontend
  - stats
  - funnel
dependencies: []
priority: high
ordinal: 218000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The board reports conversion (applied_to_interview_rate, interview_to_offer_rate, stale_applied_days) but never reports TIME or WHERE work piles up, so there is no evidence for which stage is the real bottleneck. Filed 2026-09-08 to settle that with data instead of inference: the choice between automating evaluation and speeding up submission currently rests on a reading of the code, not on measurement. This is deliberately the cheapest of the three and should land first.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Stats expose the median days from job creation to applied_at, computed only over jobs that actually reached applied
- [x] #2 Stats expose, for each actionable status, how many owner-scoped leads sit there now and the median age in that status
- [x] #3 Stats expose how many leads reached reviewed or beyond while having no JobEvaluation record
- [x] #4 A dashboard panel shows these figures and says the sample is too small rather than rendering a misleading 0 or a median over an empty set
- [x] #5 Every figure is owner-scoped and computed from real records, with synthetic backend regressions covering the median, the per-status ages, and the never-evaluated count
<!-- AC:END -->

## Measured result
<!-- SECTION:NOTES:BEGIN -->
Read off the owner's live board on 2026-09-08, not estimated:

| Figure | Value |
| --- | --- |
| Median days to applied | 8 days over 25 applications |
| new | 31 leads, median age 38 days |
| applied | 21 leads, median age 69 days |
| interview | 3 leads, median age 47 days |
| Reached past new, never evaluated | 3 |

This settles the question the task was filed to settle. Getting a found job to `applied` takes a
median of 8 days, so submission speed is not the bottleneck. The pile is 31 leads sitting in `new`
for a median of 38 days — the stall is upstream of applying, in deciding whether a lead is worth
applying to. That is evidence for TASK-220 (evaluate with the configured provider instead of
copy-paste) over any work aimed at making submission faster.

The 69-day median on `applied` is real but is mostly employers not answering, which no change here
can move; it is the reason the board already carries STALE_APPLIED_DAYS.

`reviewed` and `to_apply` hold zero leads and so are filtered out of the rendered table (the API
still returns them with count 0). AC4's small-sample and empty-cohort branches could not be observed
on live data, whose sample is 25 — they are covered by `frontend/src/stallPanel.test.tsx`, which was
falsified against a `median ?? 0` regression to confirm the assertion has teeth.
<!-- SECTION:NOTES:END -->
