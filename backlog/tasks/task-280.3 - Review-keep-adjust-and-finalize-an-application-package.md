---
id: TASK-280.3
title: 'Review, keep, adjust, and finalize an application package'
status: In Progress
assignee: []
created_date: '2026-10-12 15:03'
updated_date: '2026-10-16 07:50'
labels: []
dependencies:
  - TASK-280.2
  - TASK-278
  - TASK-279
parent_task_id: TASK-280
priority: high
type: feature
ordinal: 279000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Turn generated variants into an owner-controlled final package. Drafts must be easy to compare and edit, but generation alone must not claim that an application is ready: the owner chooses which artifacts remain and explicitly selects the package intended for submission.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The job shows recommended and fallback variants with document type, language, generation state, and PDF/TeX preview or download.
- [x] #2 The owner can mark each variant Keep or Discard, restore a discarded variant while files still exist, and select exactly one coherent final package.
- [x] #3 A kept CV, full letter, or short message can be adjusted independently through the existing adjustment paths; changing one variant leaves every other variant byte-for-byte unchanged.
- [x] #4 Copy and download actions operate on the selected variant or final package and retain the original-posting link and meaningful language/document-type filenames.
- [x] #5 Ready to submit is reached only after the owner selects a complete final package; generated-but-unreviewed jobs remain visibly drafts, and Applied/later statuses are never changed.
- [x] #6 Selection survives reload/server restart, stale selections are invalidated visibly when a selected file disappears, and frontend/backend tests cover selection, discard/restore, independent adjustment, and status transitions.
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-16: #272. Tests (31) falsified; browser check of keep/discard/select waits for the next job prepared in To apply.
<!-- SECTION:NOTES:END -->
