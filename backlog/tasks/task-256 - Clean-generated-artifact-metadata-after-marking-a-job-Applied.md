---
id: TASK-256
title: Clean generated artifact metadata after marking a job Applied
status: To Do
assignee: []
created_date: '2026-10-01 08:34'
labels:
  - backend
  - workflow
  - ux
dependencies: []
priority: medium
type: task
ordinal: 254000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner request, 2026-10-01: generated application metadata files are useful while revising an application, but should be removed once that position is marked Applied. Human-facing CV and motivation-letter filenames should not expose internal job IDs, database keys, or other implementation metadata.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 After a job is successfully changed to Applied, its generated local metadata sidecar files are deleted
- [ ] #2 Cleanup is limited to metadata for that job and never deletes its CV, motivation letter, TeX source, or another job's files
- [ ] #3 Missing metadata files or an unavailable local workspace do not undo or falsely fail the persisted Applied status
- [ ] #4 Generated CV and motivation-letter filenames omit internal job IDs, database keys, and metadata markers while retaining a clear recipient-facing document name and collision suffix when needed
- [ ] #5 Revision and artifact lookup still work before application without depending on internal metadata embedded in the human-facing filename
- [ ] #6 Tests cover Applied cleanup, isolation, missing-file behavior, simplified filenames, and collision handling
<!-- AC:END -->
