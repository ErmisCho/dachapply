---
id: TASK-346
title: Junk company names are rejected and the job board's employer is used
status: Done
assignee: []
created_date: '2026-10-25 15:39'
updated_date: '2026-10-25 15:48'
labels:
  - backend
dependencies: []
priority: medium
ordinal: 346000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found 2026-10-25 on job 1937: the analysis filled the placeholder company with 'Unknown company; posting refers to MP'. Measured: Xing, Personio (and Workday, TASK-341) pages carry schema.org JobPosting hiringOrganization.name (MP Corporate Finance GmbH, Phactum Softwareentwicklung GmbH, SQUER).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 fetch_posting_text returns the JSON-LD hiringOrganization.name as company when the site has one, so a link-only job is named at fetch time
- [x] #2 An analysis-proposed company containing 'unknown' or ';' never replaces the placeholder
- [x] #3 Tests cover both
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Merged #362. Live: fetch_posting_text on the Xing link of job 1937 returned company 'MP Corporate Finance GmbH' (JSON-LD hiringOrganization); 'Unknown company; posting refers to MP' now counts as a placeholder (test). 115 targeted tests passed.
<!-- SECTION:NOTES:END -->
