---
id: TASK-17
title: Show last update only when meaningful
status: Done
assignee:
  - '@assistant'
created_date: '2026-07-09 10:02'
updated_date: '2026-07-09 10:06'
labels: []
dependencies: []
modified_files:
  - frontend/src/App.tsx
  - backend/jobradar/serializers.py
  - backend/jobradar/tests/test_api.py
ordinal: 17000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Last update should not appear as a generic edited-at date for every job. It should only be shown/stored for active post-application states where follow-up tracking makes sense.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Dashboard hides the Last update field for statuses other than applied/interview
- [x] #2 Last update no longer falls back to updated_at
- [x] #3 Changing a job away from applied/interview clears last_update_date
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Add a tiny frontend helper for statuses that can show Last update.\n2. Hide Last update outside applied/interview and remove updated_at fallback.\n3. Make backend clear last_update_date when status leaves applied/interview and add one regression test.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Frontend now shows Last update only for applied/interview and no longer falls back to updated_at. Status changes set/clear last_update_date optimistically. Backend clears last_update_date whenever effective status is not applied/interview. Validation: backend pytest 96 passed; frontend npm run build passed.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Last update now only applies to applied/interview jobs, no longer uses updated_at as a fallback, and is cleared when status leaves those states. Verified backend pytest 96 passed and frontend build passed.
<!-- SECTION:FINAL_SUMMARY:END -->
