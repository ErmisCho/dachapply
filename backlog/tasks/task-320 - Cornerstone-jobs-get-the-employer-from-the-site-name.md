---
id: TASK-320
title: Cornerstone jobs get the employer from the site name
status: Done
assignee: []
created_date: '2026-10-19 18:45'
updated_date: '2026-10-19 20:13'
labels:
  - backend
dependencies: []
priority: medium
ordinal: 320000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Cornerstone postings (jobDetails) do not name the employer, so ÖBB jobs stay 'Unknown company'. Owner chose: fill it from the site name when the company is still a placeholder.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Reading a *.csod.com posting also yields a company name from the site (the context/corp name, mapped for known corps such as oebb -> ÖBB, otherwise the corp name title-cased)
- [x] #2 The company is written only when the job's company is a placeholder (same rule as TASK-314), never over a real name
- [x] #3 Tests cover the mapping, placeholder-only write and keep-owner-value; CI green
- [x] #4 Verified on localhost: ÖBB jobs 1845/1847 show ÖBB
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Verified on localhost 2026-10-19 (PR #309): jobs 1845/1847 show ÖBB after a fetch.
<!-- SECTION:NOTES:END -->
