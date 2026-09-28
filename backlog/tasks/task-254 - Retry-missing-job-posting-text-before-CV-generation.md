---
id: TASK-254
title: Retry missing job-posting text before CV generation
status: In Progress
assignee:
  - '@pi'
created_date: '2026-09-28 16:24'
updated_date: '2026-09-28 16:40'
labels:
  - backend
  - frontend
  - data
  - ai
dependencies: []
modified_files:
  - .orchestrator/debug/01a0e859-192d-77f4-aed0-df74ffce7244-3.md
  - backend/jobradar/tests/test_api.py
  - backend/jobradar/services/cv_tasks.py
priority: high
type: bug
ordinal: 252000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
When a job was imported without collecting its original posting text, the CV/letter workflow should make one best-effort retry against the job URL before generation so the generated documents use the posting rather than a fallback summary whenever retrieval is possible.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Before generation, a job with no collected original posting text and a usable source URL gets one retrieval attempt
- [x] #2 When retrieval succeeds, the retrieved posting is saved and the same text is used by that generation
- [x] #3 Existing collected or user-corrected source text is never fetched again or overwritten
- [x] #4 When retrieval fails, no placeholder or synthetic text is persisted and generation can continue with the existing honestly-labelled fallback
- [x] #5 Regression tests cover successful retry, skipped retry, and failed retry behavior
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Add one private helper at the shared CV worker boundary that skips meaningful originals and linkless jobs, otherwise reuses the existing guarded posting fetcher once.
2. On success, persist with a compare-and-set against the original value so a concurrent user edit wins; use the resulting latest row for the same generation. On failure, write nothing and keep the fallback.
3. Add direct worker regressions for success/use, existing-source skip, failure fallback, and concurrent-edit preservation.
4. Run focused and full gates, Asian Dad evaluation, browser verification only if the behavior has a user-visible UI surface, then commit, push, squash-merge, and close TASK-254.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Root cause documented: the guarded fetcher exists only behind the manual read-only endpoint; the shared CV worker loads the job and immediately generates without retrying. Groma task links are unavailable in this clean worktree because the first-scan groma directory is untracked in the owner's dirty main checkout.

Added one direct-worker regression covering successful fetch/save/use, meaningful-source skip, failed-fetch fallback, and a concurrent user edit winning over the automatic retry.

Implemented the retry once in the shared worker using the existing guarded fetcher. Successful text is compare-and-set into the missing original field, then the job is refreshed so concurrent manual edits win; failures write nothing.

Focused backend verification passed: test_api.py plus test_posting_fetch.py, 288 tests. The regression asserts exactly one attempt on both success and honest failure.

Full gates passed: 1,235 backend tests; 306 frontend tests; TypeScript/Vite production build. npm ci reported two pre-existing moderate vulnerabilities; build retained the existing chunk-size warning.

Asian Dad evaluation: PERFECT (self-graded). The worker regression measured one fetch before generation, exact fetched-text persistence/use, no fetch for meaningful originals, no write on failure, fallback continuation, and concurrent-edit preservation.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Before any model-backed CV or letter task, the shared worker now makes one guarded best-effort posting fetch when the durable original text is missing. Meaningful results are race-safely saved and used immediately; existing/corrected text is untouched, and failures preserve the current fallback. Verified by the direct worker regression, 1,235 backend tests, 306 frontend tests, and the production frontend build.
<!-- SECTION:FINAL_SUMMARY:END -->
