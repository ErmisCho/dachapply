---
id: TASK-30
title: Preserve original full job text from ChatGPT collection
status: Done
assignee:
  - '@pi'
created_date: '2026-07-15 15:41'
updated_date: '2026-07-16 11:08'
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
- [x] #6 AI evaluation, enrichment, and CV generation use the original source text with legacy fallback
- [x] #7 CV and letter language defaults are detected from the original source text
- [x] #8 ChatGPT JSON replaces an empty or link-only placeholder snapshot with the first complete job text
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Add the database field and migration, extend import schemas and portability, preserve first-write semantics, and add regression tests.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Added immutable original_source_text storage with a migration that backfills existing raw descriptions. ChatGPT bulk schemas request complete untruncated source text; new JSON imports retain it, while model-level first-write preservation prevents later edits/enrichment from replacing it. CV revisions now use the full original snapshot. Authenticated JSON/CSV/XLSX portability includes the field. Validation passed: 40 import/export/prompt tests, Django check, migration drift check, and git diff check.

Follow-up: make the immutable original source text the source document for AI prompts and CV/letter language detection, while retaining raw_description only as fallback for legacy/empty snapshots.

Added a single JobLead.source_text source-of-truth property. Evaluation, combined/enrichment prompts, CV generation, language detection, job-detail display, and dashboard search now prefer the immutable original snapshot and only fall back to raw_description for empty legacy records. Prompt truncation was removed so AI receives the complete source document. Focused tests, frontend build, Django check, migration drift check, and whitespace check passed.

Bug follow-up: link-only intake can occupy the immutable snapshot before ChatGPT JSON supplies the full text. Preserve immutability only after meaningful job text arrives, then verify language detection from the imported snapshot.

Fixed the link-first intake edge case: URL-only text no longer becomes an authoritative snapshot, and ChatGPT JSON can replace existing empty/link-only placeholders with the first meaningful original_source_text or raw_description. Once meaningful text is stored it remains immutable. CV/letter language detection immediately reads that imported source. Added an end-to-end regression test covering import, German detection, and attempted overwrite. Full validation passed: 110 backend tests, frontend build, Django check, migration drift check, and whitespace check.

Specific diagnosis: job #440 stored two English summaries rather than the German page text, so the detector correctly saw English. Repair the record and strengthen collection prompts to require verbatim original-language content.

Repaired TÜV AUSTRIA Machine Learning Engineer job #440 from its public source URL: original_source_text now contains 3,131 characters of German page text and detect_job_language returns de. Combined, enrichment, and bulk-link prompts now explicitly require opening the URL and copying the complete posting verbatim in its original language without translation, summary, rewriting, or truncation. Four focused regression tests and Django check passed.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Original-language collection is now explicit and the affected TÜV job has its actual German source text restored; CV/letter detection reports German.
<!-- SECTION:FINAL_SUMMARY:END -->
