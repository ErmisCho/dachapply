---
id: TASK-223
title: Refuse duplicate evaluations for the same job in one model run
status: To Do
assignee: []
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
- [ ] #1 A model response containing two entries for the same job_id is rejected, or collapsed to one, by an explicit decision recorded in the code rather than by accident of iteration order
- [ ] #2 The count offered on the commit button equals the number of jobs that would actually be written, for every response the preview will accept
- [ ] #3 A commit cannot write more JobEvaluation rows for a job than the run evaluated it times, verified against the database rather than the response
- [ ] #4 A synthetic regression covers a duplicated job_id without calling a real provider, and fails if the guard is removed
- [ ] #5 The existing single-evaluation and multi-job paths are unchanged, evidenced by the current tests still passing untouched
<!-- AC:END -->

## Notes
<!-- SECTION:NOTES:BEGIN -->
Reproduction, 2026-09-09, on the owner's machine with `lms server start` running:

1. Select exactly one job on the board.
2. Evaluate with model, provider `lmstudio`, model `deepseek-r1-distill-qwen-7b`, effort `default`,
   speed `normal`.
3. Press Preview evaluation. It returned in ~24s with two rows for the one selected job.

Nothing was saved — the run was closed without pressing Save, so no duplicate reached the database.
<!-- SECTION:NOTES:END -->
