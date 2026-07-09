---
id: TASK-12
title: Show demo users separately in Django admin
status: Done
assignee:
  - '@assistant'
created_date: '2026-07-02 15:37'
updated_date: '2026-07-02 15:40'
labels: []
dependencies: []
modified_files:
  - backend/jobradar/admin.py
  - backend/templates/admin/auth/user/change_list.html
  - backend/jobradar/tests/test_api.py
ordinal: 12000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The Django admin user changelist should keep demo-related users visually separate from real users so usage/admin review is clearer.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Demo-related users are excluded from the main users changelist
- [x] #2 Demo-related users appear in a separate table underneath the users table with links to edit them
- [x] #3 Relevant admin rendering check passes
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Reuse existing demo account/profile relationships to identify demo-related users.\n2. Exclude those users from the main User changelist.\n3. Render a small separate demo-users table below the main admin users table.\n4. Add one admin changelist rendering test.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Admin User changelist now identifies demo-related users from demo@dachapply.com plus UserProfile submit_for/requested_submit_for links, excludes them from the main changelist, and renders them in a Demo users table below pagination with edit links. Added an admin rendering regression test. Tests: DATABASE_URL= DEBUG=True DB_ENGINE=django.db.backends.sqlite3 DB_NAME=:memory: python -m pytest -q (92 passed).
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Separated demo-related users from the main Django admin users list and added a Demo users table underneath it. Verified with admin rendering test and full backend test suite.
<!-- SECTION:FINAL_SUMMARY:END -->
