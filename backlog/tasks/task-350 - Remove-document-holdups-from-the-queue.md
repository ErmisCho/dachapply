---
id: TASK-350
title: Remove document holdups from the queue
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
Owner approved after a measured review: 8 of 20 blocked jobs were missing only the salary, 5 were stuck on a failed re-analysis until Retry, and a Ready to submit job showed 'Posting incomplete'.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A posting missing only the salary no longer holds documents back; they prepare normally.
- [x] #2 A missing salary stays visible as a note and is not silently dropped; postings missing tasks, requirements or company description still hold as before.
- [x] #3 A re-analysis that fails with a transient error retries by itself, with a fixed cap and a delay; after the cap it stays failed and visible.
- [x] #4 A job in Ready to submit never shows a 'Posting incomplete' hold.
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Verified on the real queue with disposable sqlite: a salary-only job prepared its CV and 3 letters, a thin posting still held, Ready to submit showed no hold. Transient re-analysis retries twice, 10 minutes apart, and a Pause spends none (tests with a fake clock). The 5 real failed re-analyses could not be classified: the provider detail is not stored.
<!-- SECTION:NOTES:END -->
