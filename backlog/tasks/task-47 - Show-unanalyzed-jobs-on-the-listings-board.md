---
id: TASK-47
title: Show unanalyzed jobs on the listings board
status: Done
assignee: []
created_date: '2026-07-23 14:33'
updated_date: '2026-07-23 14:34'
labels: []
dependencies: []
modified_files:
  - frontend/src/App.tsx
ordinal: 48000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Newly saved jobs currently disappear from the main board because the dashboard requests analyzed=1. Users need every saved listing, including the new EBCONT (BMJ) details-only job, to be visible immediately.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Newly saved jobs without an evaluation appear on the main listings board
- [x] #2 Unanalyzed rows display their company and title with empty analysis fields
- [x] #3 Existing board filters continue to apply
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Stop forcing the analyzed-only filter in the dashboard request.
2. Build the frontend and verify the EBCONT job is returned by the board query.
3. Refresh the served frontend.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Removed the dashboard-only analyzed=1 query parameter. This intentionally changes TASK-15 behavior based on the latest user requirement: unanalyzed listings now appear as regular board rows with blank fit/analysis fields, while the existing filters remain unchanged.

Validation: frontend npm run build passed; owner-visible default-status query returns job #709 EBCONT (BMJ) / ElasticSearch Consultant; Django now serves the new frontend bundle; health is 200/database ok.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
The main listings board now includes newly saved unanalyzed jobs, including EBCONT (BMJ), instead of hiding them until evaluation.
<!-- SECTION:FINAL_SUMMARY:END -->
