---
id: TASK-30
title: Preserve original full job text from ChatGPT collection
status: Done
assignee:
  - '@pi'
created_date: '2026-07-15 15:41'
updated_date: '2026-07-16 06:54'
labels:
  - backend
  - data
dependencies:
  - TASK-29
modified_files:
  - backend/jobradar/models.py
  - backend/jobradar/migrations/0019_joblead_original_source_text.py
  - backend/jobradar/services/json_importer.py
  - backend/jobradar/services/user_data_portability.py
  - backend/jobradar/services/prompt_builder.py
  - backend/jobradar/services/cv_generator.py
  - backend/jobradar/tests/test_api.py
priority: high
ordinal: 30000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Each job stores an immutable original full-text snapshot collected through the link/ChatGPT workflow separately from the editable cleaned description.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Job records have a dedicated original source text field
- [x] #2 Bulk link and ChatGPT imports populate the full original text without application-side truncation
- [x] #3 Later enrichment or edits do not overwrite an existing original snapshot
- [x] #4 Original text is included in authenticated data export/import
- [x] #5 Migration and tests preserve existing jobs and verify snapshot immutability
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Add the database field and migration, extend import schemas and portability, preserve first-write semantics, and add regression tests.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Added immutable original_source_text storage with a migration that backfills existing raw descriptions. ChatGPT bulk schemas request complete untruncated source text; new JSON imports retain it, while model-level first-write preservation prevents later edits/enrichment from replacing it. CV revisions now use the full original snapshot. Authenticated JSON/CSV/XLSX portability includes the field. Validation passed: 40 import/export/prompt tests, Django check, migration drift check, and git diff check.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Job records now preserve a full immutable original source snapshot separately from editable descriptions, carry it through collection and portability, and use it as CV-generation context.
<!-- SECTION:FINAL_SUMMARY:END -->
