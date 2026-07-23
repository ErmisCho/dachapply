---
id: TASK-48
title: Hide link-only untitled jobs from the listings board
status: Done
assignee: []
created_date: '2026-07-23 14:36'
updated_date: '2026-07-23 14:39'
labels: []
dependencies:
  - TASK-47
modified_files:
  - backend/jobradar/views.py
  - backend/jobradar/tests/test_api.py
  - frontend/src/App.tsx
ordinal: 49000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The board should show newly saved details-only jobs such as EBCONT, but raw captured links that still have no real title should stay in the analysis queue and not appear as board rows.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A URL-only job with the default or blank title is hidden from the board
- [x] #2 An unanalyzed job with a real title remains visible on the board
- [x] #3 Hidden link-only jobs remain available to the analysis workflow
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Add a dashboard-specific API filter that excludes blank/default titles.
2. Make the dashboard use that filter while leaving the analysis queue unfiltered.
3. Add regression coverage, build, and restart the local app.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Added board=1 filtering: blank titles and generated Untitled role titles are excluded only from board queries. The dashboard uses this filter; its separate status=new analysis query remains unfiltered.

Validation: 124 backend tests passed on local SQLite; frontend build passed. Live owner data check shows EBCONT #709 visible, zero untitled rows on the board, and 22 untitled jobs still in the analysis queue. Restarted localhost; health is 200/database ok.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
The board now shows named unanalyzed jobs such as EBCONT while hiding link-only jobs until they receive a real title; those links remain available for analysis.
<!-- SECTION:FINAL_SUMMARY:END -->
