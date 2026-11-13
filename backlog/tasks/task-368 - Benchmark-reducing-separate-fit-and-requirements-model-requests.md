---
id: TASK-368
title: Benchmark reducing separate fit and requirements model requests
status: Done
assignee: []
created_date: '2026-11-11 15:24'
updated_date: '2026-11-13 07:12'
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
- [x] #1 A matched representative posting set compares the current separate path and a combined candidate, recording provider requests, elapsed time, failures and output-quality differences with identical model settings.
- [x] #2 Compare fit verdicts and source-grounded application requirements, including missing/ambiguous postings, explicit language, required/unwanted letters and skip decisions; parser/schema validity alone is not the quality bar.
- [x] #3 Owner-edited requirements, late posting updates, failure isolation, cancellation and strict import validation remain authoritative.
- [x] #4 No request is repeated just because valid requirements are already stored; retained or rejected combinations are documented with measured evidence, not a promised percentage saving.
- [x] #5 Do not change the current production default unless the measured benefit and labelled quality comparison support it; any approved change leaves regression coverage.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Add an isolated fit_requirements experiment using existing fit/requirements services, strict validation and matched settings. 2. Add per-job review output and paired-result review command. 3. Verify with hermetic fakes, backend suite and frontend checks; document owner measurement handoff without changing defaults or task status.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Built benchmark_fit_requirements as an isolated registered experiment with separate/combined variants, original fit importer validation and requirements schemas/quote normalisation, matched CV model settings, stored-owner requirements reuse, late-change discard, cancellation and per-job failure isolation. Added harness review hook and signature-preserving request wrappers, benchmark_fit_review to pair runs into side-by-side review.md, hermetic fake-provider coverage, and coordinator/owner run and quality-labelling instructions. No production path/default changes; no task status or acceptance checkbox changes.
\n2026-11-13 result (real models, gpt-6.1-sol high, 5 exported jobs, scratch DB):\n- Only job 2083 lacked stored requirements, so only it exercised the combined path: separate 2 requests / 106 s, combined 1 request / 77 s. The other 4 jobs ran one fit request in both arms (the 389 s vs 75 s gap on job 2079 is provider variance on an identical request), so the 1028 s vs 491 s totals are not attributable to the change.\n- Quality: identical recommendations and skip decisions on all 5 jobs; fit scores within 1-8 points. On job 2083 they disagreed: separate marked a short message as required, combined did not; the owner checked the posting and judged combined correct (a general invitation, not a required message).\n- Decision: keep the separate default. The benefit is one request on 1 of 5 jobs (n=1); retest with more jobs that need fresh requirements before changing anything.\n- Review note: pairing checks fixture path, not content (Codex P2); both arms used the same fixture here.
<!-- SECTION:NOTES:END -->
