---
id: TASK-323
title: A more complete fetched posting replaces an incomplete stored one
status: In Progress
assignee: []
created_date: '2026-10-19 20:02'
labels:
  - backend
dependencies: []
priority: high
ordinal: 323000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Live 2026-10-19: ÖBB job 1847's stored text (1368 chars, Cornerstone API description only) lacks requirements and salary; a headless re-read returns the full ad (7053 chars). The thin-only rule (TASK-313) staged it for review. Owner chose: replace automatically when the stored text is missing parts and the fetched one misses fewer; a text with all four parts still needs review.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Every fetch path saves a fetched posting directly when the stored text lacks a required part (TASK-322 missing_parts) and the fetched text lacks fewer; a stored text with all four parts keeps the review step
- [ ] #2 Pre-analysis fetch and the Queue's blocked Retry also re-fetch jobs whose stored text is incomplete, so Retry on 'Posting incomplete' can resolve it
- [ ] #3 Tests cover replace-when-fuller, keep-review-when-complete, Retry re-fetching an incomplete job; revert-checked; CI green
- [ ] #4 Verified on localhost: ÖBB jobs 1845/1847 get the full ad
<!-- AC:END -->
