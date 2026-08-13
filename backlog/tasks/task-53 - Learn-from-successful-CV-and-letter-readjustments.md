---
id: TASK-53
title: Learn from successful CV and letter readjustments
status: Done
assignee:
  - '@pi'
created_date: '2026-07-28 11:32'
updated_date: '2026-07-31 10:58'
labels: []
dependencies: []
modified_files:
  - backend/jobradar/models.py
  - >-
    backend/jobradar/migrations/0020_userprofile_learned_application_preferences.py
  - backend/jobradar/serializers.py
  - backend/jobradar/services/cv_generator.py
  - backend/jobradar/services/cv_tasks.py
  - backend/jobradar/services/user_data_portability.py
  - backend/jobradar/views.py
  - backend/jobradar/tests/test_api.py
  - frontend/src/App.tsx
  - frontend/src/types/index.ts
priority: high
ordinal: 54000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Persist each account's successful CV/letter readjustment instructions as reusable application preferences so future document generations need less repeated correction. Only successful revisions should be learned; job-specific generation output itself is not treated as a global preference.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 After a successful CV-only, letter-only, or combined readjustment, the account stores the instruction with its document scope without duplicating an identical learned entry
- [x] #2 Future CV/letter generations for that account include the learned preferences, while other accounts do not
- [x] #3 Failed readjustments do not change learned preferences
- [x] #4 The account owner can review, edit, or clear learned preferences from Profile settings and they are included in account data export/import
- [x] #5 Backend tests and frontend build pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Add an account-level learned application preferences field and include it in profile serialization/portability.\n2. Add learned preferences to CV generation context only.\n3. Record scoped revision instructions after successful background generation.\n4. Expose the field in Profile settings and add focused tests.\n5. Run backend tests and frontend build.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented the minimum learning loop: successful readjustment instructions are normalized, scoped to CV/letter/both, deduplicated, and saved per UserProfile. Future document prompts include them below mandatory evidence/rules. Initial job-specific generation output is intentionally not learned globally. Validation: 125 backend tests passed; frontend production build passed; makemigrations --check reported no changes.

Applied migration 0020 to the configured local-development database after authenticated /api/auth/me/ failed on the missing learned_application_preferences column; verified /api/auth/me/ returns 200 for the affected account.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Added account-scoped CV/letter preference learning from successful readjustments, editable Profile settings, prompt reuse, export/import support, migration, UI confirmation, and focused coverage. Verified with 125 backend tests and the frontend production build.
<!-- SECTION:FINAL_SUMMARY:END -->
