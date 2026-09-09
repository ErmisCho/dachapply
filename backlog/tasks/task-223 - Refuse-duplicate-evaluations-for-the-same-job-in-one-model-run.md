---
id: TASK-223
title: Refuse duplicate evaluations for the same job in one model run
status: Done
assignee:
  - '@ErmisCho'
created_date: ''
updated_date: '2026-09-09 14:16'
labels:
  - backend
  - llm
  - evaluation
dependencies: []
priority: medium
ordinal: 222000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Filed 2026-09-09 from TASK-221's verification, and observed in the real app rather than reasoned from
the code. One job was selected on the board and evaluated through
`lmstudio / deepseek-r1-distill-qwen-7b`. The dry-run preview came back with the **same job twice** —
two identical rows, `fit 90 / high / apply`, each saying "Replaces current fit 94" — and the commit
button offered to **"Save 2 evaluations"** for one selected job.

The cause is in `jobradar/services/job_evaluator.py::evaluate_jobs`, which TASK-220 added. It
validates every entry in the model's `evaluations` list against the set of requested job ids, but
nothing requires those ids to be *distinct*:

    preview = [_preview_row(requested[ev['job_id']], ev) for ev in data['evaluations']]

A model that emits the same `job_id` twice therefore produces two preview rows and, on commit, two
writes through `import_evaluations`. The board reads the newest evaluation, so the visible damage is
a misleading count and a duplicated history row rather than a wrong ranking — but the count is what
the owner is asked to approve, so it should not be able to lie.

This is a provider-agnostic defect. A local model exposed it because local models honour a schema
loosely (the same looseness that made `parse_json_object` necessary in TASK-221), but nothing in the
code prevents a cloud model from doing it, and nothing in the schema forbids it either.

Not fixed inside TASK-221: different file territory, and the shared `evaluate_jobs` path is
TASK-220's, so a change here needs its own acceptance criteria and its own regression.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A model response containing two entries for the same job_id is rejected, or collapsed to one, by an explicit decision recorded in the code rather than by accident of iteration order
- [x] #2 The count offered on the commit button equals the number of jobs that would actually be written, for every response the preview will accept
- [x] #3 A commit cannot write more JobEvaluation rows for a job than the run evaluated it times, verified against the database rather than the response
- [x] #4 A synthetic regression covers a duplicated job_id without calling a real provider, and fails if the guard is removed
- [x] #5 The existing single-evaluation and multi-job paths are unchanged, evidenced by the current tests still passing untouched
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. In job_evaluator.py::evaluate_jobs, track seen job_id -> index while validating entries. 2. On a repeat job_id, reject the whole response with an explicit error naming both entries, rather than collapsing to one (a model that contradicts itself about one job in one response is not trustworthy input, and collapsing would hide that plus make the kept row a function of list order). 3. Add test_evaluation_duplicates.py: same job twice is rejected (not collapsed); a duplicated response commits nothing, verified against the DB; the previewed count equals rows actually written for a normal two-job response.
<!-- SECTION:PLAN:END -->

## Implementation Notes

Implemented and verified 2026-09-09. 3/3 new tests pass (`test_evaluation_duplicates.py`), reusing
`test_job_evaluator`'s fixtures and response builder so a rejection here is only ever about the
duplicate and never about a differently-shaped payload.

**Verified by the coordinator independently of the implementing agent**, per TW-003:

- With `elif job_id in seen:` disabled, **2 of the 3 new tests fail**; restored, 19 pass. The
  regression is real rather than vacuous.
- Row counts are asserted against the database (`JobEvaluation.objects.filter(...).count()`), not
  against the response, as AC3 requires.
- No pre-existing test was modified — AC5 is about the old tests passing *untouched*, and they do.
- AC2 needed no frontend change: the button renders ``Save ${previewRows.length} evaluation`` from
  `result.preview` (`frontend/src/App.tsx:401`), and rejecting duplicates means every accepted
  preview has distinct ids, so the count is the number of rows a commit writes.

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
evaluate_jobs now rejects a model response containing two entries for the same job_id (reject, not collapse — recorded as a deliberate decision in the code comment, since two entries are two different verdicts and collapsing would hide a model that contradicts itself). Verified: a duplicated job_id fails validation with an explicit error naming both entries; a duplicated response commits zero rows even when the caller passes commit=True, checked against JobEvaluation.objects.count() rather than the response; the previewed count for a normal two distinct-job response equals both result['created'] and the DB row count. Existing test_job_evaluator suite passes unchanged.
<!-- SECTION:FINAL_SUMMARY:END -->

## Notes
<!-- SECTION:NOTES:BEGIN -->
Reproduction, 2026-09-09, on the owner's machine with `lms server start` running:

1. Select exactly one job on the board.
2. Evaluate with model, provider `lmstudio`, model `deepseek-r1-distill-qwen-7b`, effort `default`,
   speed `normal`.
3. Press Preview evaluation. It returned in ~24s with two rows for the one selected job.

Nothing was saved — the run was closed without pressing Save, so no duplicate reached the database.
<!-- SECTION:NOTES:END -->
