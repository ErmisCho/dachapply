---
id: TASK-20
title: Include application outcomes in AI-ready exports
status: Done
assignee:
  - '@pi'
created_date: '2026-07-15 09:20'
updated_date: '2026-07-15 09:21'
labels:
  - backend
  - export
dependencies: []
priority: medium
ordinal: 20000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Application statuses and outcome dates must be stored and included in exports so users can give their application history to ChatGPT for analysis.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 JSON and CSV job exports include the stored status and relevant status/interview dates
- [x] #2 The ChatGPT brief identifies each job's status and relevant dates or interview stage
- [x] #3 Tests verify rejected and interview outcomes are extractable
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Extend the existing exporters with the already-stored status metadata. 2. Add focused export tests. 3. Run the backend export tests.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Extended the existing exporters rather than adding a second analysis format. Focused export tests passed: 3 passed, 93 deselected. Pytest emitted an existing demo scheduler database-access traceback and teardown warning, but the selected tests passed.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Application status, outcome date, interview stage, last update, and feedback due date are now included in JSON, CSV, and ChatGPT brief exports. Verified rejected and interview outcomes with focused API tests.
<!-- SECTION:FINAL_SUMMARY:END -->
