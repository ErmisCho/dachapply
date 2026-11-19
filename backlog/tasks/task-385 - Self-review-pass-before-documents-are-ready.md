---
id: TASK-385
title: Self-review pass before documents are ready
status: Done
assignee: []
created_date: '2026-11-18 22:37'
updated_date: '2026-11-19 06:34'
labels: []
dependencies: []
priority: high
ordinal: 386000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
After generation compiles, one reviewer model call (same provider/model/effort the run used; never local when the account is cloud-only) checks CV+letter against a fixed rubric (unsupported claims, posting's top requirements reflected in headline/profile, page fit, letter not repeating CV bullets, stray instruction text, language) and returns OLD/NEW fixes that are applied through the existing exact OLD/NEW path, then recompiled. Bounded to one review round. Evidence: adjustments.jsonl 2026-10-21..11-18, 130 Adjusts over 34 jobs (median 3 ready Adjusts/job); audits in jobs/6526c3ef/tmp (optimization-audit.md, ux-audit.md). Owner approved 2026-11-18.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A generation run calls the reviewer once after a successful compile and before the task turns ready; a test proves the call happens exactly once per run and never on Adjust/revise runs
- [x] #2 Reviewer fixes are applied only through exact_revision_plan/match_exact_pair semantics (unique or every-copy match, byte-local); a fix whose OLD does not match is dropped and reported, never applied fuzzily
- [x] #3 After applying fixes the documents are recompiled and page limits re-checked; if compile or page check fails, the pre-review files are kept and the run still ends ready with a note
- [x] #4 The task report lists each applied and dropped finding; reviewer failure/timeout never fails the run
- [x] #5 Setting/flag allows turning the pass off; default on
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
PR #432. Real reviewer run on job 2086 documents (gpt-6.1-sol, read-only): 33-45 s, 10 findings; first run showed the word gate blocking prose and the reviewer stripping true template facts -> fixed (claim-like token gate; base templates passed as owner-written evidence). Full in-app generation with the review not yet observed.
<!-- SECTION:NOTES:END -->
