---
id: TASK-11
title: Limit demo job listings to demo account
status: Done
assignee:
  - '@assistant'
created_date: '2026-07-02 15:25'
updated_date: '2026-07-02 15:32'
labels: []
dependencies: []
modified_files:
  - backend/jobradar/services/demo_data.py
  - backend/jobradar/management/commands/seed_demo.py
  - backend/jobradar/tests/test_api.py
ordinal: 11000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Demo job listings must only be present for the demo account; any demo listings accidentally assigned to other accounts should be removed.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Demo seed/import code only creates demo job listings for the demo account
- [x] #2 Existing demo job listings assigned to non-demo accounts are removed
- [x] #3 Relevant tests or checks pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Find where demo job listings are seeded or imported.\n2. Change the code so demo listings are scoped to the demo account only.\n3. Delete existing demo listings belonging to non-demo accounts.\n4. Run the smallest relevant checks.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Changed demo seeding so all seeded demo jobs, including friend-referral examples, are owned by demo@dachapply.com. Added cleanup for leaked demo URL/source rows and the legacy example.com Dynatrace seed row. Ran seed_demo against configured DB; verification shows 9 demo jobs, 3 friend-source jobs, 0 external demo-like jobs. Tests: DATABASE_URL= DEBUG=True DB_ENGINE=django.db.backends.sqlite3 DB_NAME=:memory: python -m pytest -q (91 passed).
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Demo seed now scopes demo listings to the demo account, cleans leaked demo rows from other accounts, and the configured DB was reseeded/verified clean. Tests passed: 91.
<!-- SECTION:FINAL_SUMMARY:END -->
