---
id: TASK-350
title: Remove document holdups from the queue
status: To Do
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
- [ ] #1 A posting missing only the salary no longer holds documents back; they prepare normally.
- [ ] #2 A missing salary stays visible as a note and is not silently dropped; postings missing tasks, requirements or company description still hold as before.
- [ ] #3 A re-analysis that fails with a transient error retries by itself, with a fixed cap and a delay; after the cap it stays failed and visible.
- [ ] #4 A job in Ready to submit never shows a 'Posting incomplete' hold.
<!-- AC:END -->
