---
id: TASK-346
title: Junk company names are rejected and the job board's employer is used
status: To Do
assignee: []
created_date: '2026-10-25 15:39'
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
- [ ] #1 fetch_posting_text returns the JSON-LD hiringOrganization.name as company when the site has one, so a link-only job is named at fetch time
- [ ] #2 An analysis-proposed company containing 'unknown' or ';' never replaces the placeholder
- [ ] #3 Tests cover both
<!-- AC:END -->
