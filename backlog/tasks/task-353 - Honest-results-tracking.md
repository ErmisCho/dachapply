---
id: TASK-353
title: Honest results tracking
status: Done
assignee: []
created_date: '2026-11-06 12:30'
labels:
  - owner-review
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner approved after a measured review: the funnel shows 3 interviews while 5 exist, because 5 interview jobs have no application date, and fit score has not predicted interviews so far.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Interview jobs with no application date count in the funnel, so it reports every job that reached interview.
- [x] #2 Stats show applications, interviews and rejections by fit score band, including jobs with no score.
- [x] #3 The view states how many applications are still waiting, so a small sample is not read as a conclusion.
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Verified on disposable data: the funnel counts undated interviews, fit bands match the seeded jobs, and the waiting count is stated on the Stats page. Real-account numbers not re-measured.
<!-- SECTION:NOTES:END -->
