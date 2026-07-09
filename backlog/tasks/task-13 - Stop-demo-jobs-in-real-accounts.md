---
id: TASK-13
title: Stop demo jobs in real accounts
status: Done
assignee:
  - '@assistant'
created_date: '2026-07-08 15:35'
updated_date: '2026-07-08 15:43'
labels:
  - bug
  - frontend
  - backend
dependencies: []
modified_files:
  - frontend/src/App.tsx
  - backend/jobradar/services/demo_data.py
  - backend/jobradar/serializers.py
  - backend/jobradar/services/json_importer.py
  - backend/jobradar/views.py
  - backend/jobradar/migrations/0018_delete_non_demo_demo_jobs.py
  - backend/jobradar/tests/test_api.py
priority: high
ordinal: 13000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Real user accounts, including ermis.chorinopoulos@gmail.com, must not receive demo/sample job listings. The frontend empty-state demo action currently creates source=demo jobs in the signed-in account; remove that path and clean leaked demo rows from non-demo users.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Real users cannot add the built-in demo sample jobs to their own dashboard
- [x] #2 Existing source=demo or demo.dachapply.local jobs outside demo@dachapply.com are removed during deployment/seed cleanup
- [x] #3 Regression tests cover non-demo cleanup/prevention
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Remove the dashboard empty-state action that posts demo samples into the signed-in account.\n2. Add a backend guard and migration cleanup for source=demo/demo.dachapply.local rows outside demo@dachapply.com.\n3. Add the smallest regression test and run focused checks.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Removed the authenticated empty-dashboard demo-data creator. Added API/import validation so non-demo users cannot create source=demo or demo.dachapply.local jobs. Added a data migration and shared cleanup to delete leaked demo jobs outside demo@dachapply.com. Checks: backend pytest 93 passed; frontend npm run build passed.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Real accounts no longer get demo sample jobs: the UI action is gone, backend creation/import rejects demo payloads for non-demo users, and migration/seed cleanup removes leaked rows. Verified with backend tests and frontend build.
<!-- SECTION:FINAL_SUMMARY:END -->
