---
id: TASK-41
title: Preserve job-identifying URL query parameters
status: Done
assignee:
  - '@pi'
created_date: '2026-07-18 11:47'
updated_date: '2026-07-18 11:49'
labels:
  - backend
  - bug
dependencies: []
modified_files:
  - backend/jobradar/serializers.py
  - backend/jobradar/services/json_importer.py
  - backend/jobradar/tests/test_api.py
priority: high
ordinal: 42000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Bulk job entry currently strips every URL query parameter, collapsing distinct postings such as StraBAG ReqId links into one duplicate. Preserve identifying parameters while continuing to remove common tracking parameters.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Three links with the same path and different ReqId values create three separate jobs
- [x] #2 Common utm tracking parameters remain ignored for duplicate detection
- [x] #3 JSON imports use the same URL normalization behavior
- [x] #4 Focused API tests pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Fix the shared URL normalizer to retain non-tracking query parameters, reuse it from JSON import, and add a regression test using the reported ReqId links.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
URL normalization now preserves non-tracking query parameters such as ReqId while removing utm/utm_*, fbclid, gclid, and msclkid. JSON import reuses the same normalizer instead of maintaining a divergent copy. Regression tests cover all three reported STRABAG links, tracking-only duplicate behavior, and JSON import. Four focused tests, Django check, and diff check pass.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Distinct job IDs carried in URL query parameters no longer collapse into one duplicate; the three reported links create three jobs while tracking parameters remain ignored.
<!-- SECTION:FINAL_SUMMARY:END -->
