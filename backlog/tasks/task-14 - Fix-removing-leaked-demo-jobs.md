---
id: TASK-14
title: Fix removing leaked demo jobs
status: Done
assignee:
  - '@assistant'
created_date: '2026-07-09 09:31'
updated_date: '2026-07-09 09:35'
labels: []
dependencies: []
modified_files:
  - backend/jobradar/serializers.py
  - backend/jobradar/tests/test_api.py
ordinal: 14000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Removing demo job listings from the ermis.chorinopoulos@gmail.com account currently sends PATCH /api/jobs/<id>/ and returns 400, leaving leaked demo rows visible. Fix the shared job update/delete path so these rows can be removed or archived without validation errors.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Affected demo job rows on a normal user account can be removed from the UI without 400 responses
- [x] #2 The fix does not allow users to modify jobs owned by other accounts
- [x] #3 A backend regression check covers the failing remove/archive request
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Reproduce the failing PATCH with the backend API and inspect the 400 response.\n2. Fix the shared job update/remove path at the smallest point.\n3. Add one backend regression check for removing/archiving the affected rows and run it.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Fixed JobLeadSerializer demo validation to reject only incoming demo URL/source values, so existing leaked owned rows can be archived by status PATCH. Added regression coverage for archiving a leaked demo row and for blocking PATCH-to-demo on a normal row. Tests: cd backend && DACHAPPLY_DEMO_SEED_SCHEDULER=0 DATABASE_URL= DEBUG=True DB_ENGINE=django.db.backends.sqlite3 DB_NAME=:memory: ../.venv/Scripts/python.exe -m pytest -q (94 passed).
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Allowed archived-status PATCHes for owned leaked demo rows by validating only incoming demo URL/source values. Added regression coverage for archiving a leaked demo job and preserving the create/PATCH-to-demo block. Verified: backend pytest 94 passed.
<!-- SECTION:FINAL_SUMMARY:END -->
