---
id: TASK-311
title: Fetched posting text is queued for review only on jobs being applied to
status: To Do
assignee: []
created_date: '2026-10-18 22:36'
updated_date: '2026-10-18 23:02'
labels: []
dependencies: []
ordinal: 312000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner (2026-10-19): 26 of 35 open jobs showed 'fetched text waiting'. The daily refresh re-fetches every job with a URL, of every status, and stages any copy that differs from the saved text, which is the structured extract, so it nearly always differs.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The automatic refresh (refresh-due) only fetches jobs in New, Reviewed, To apply or Ready to submit; Applied and later are never re-fetched automatically
- [x] #2 On a To apply or Ready to submit job a differing fetched copy is staged for review exactly as today
- [x] #3 On a New or Reviewed job: when the saved text is not a usable posting (JobLead.is_meaningful_source false) the fetched text is saved as the job text directly; otherwise the saved text is kept, nothing is staged, and a copy staged earlier is cleared
- [x] #4 A manual fetch (POST job_source_text_live) still stages a differing copy on any status
- [x] #5 Tests cover each branch and each fails when its logic is removed; backend suite passes
<!-- AC:END -->
