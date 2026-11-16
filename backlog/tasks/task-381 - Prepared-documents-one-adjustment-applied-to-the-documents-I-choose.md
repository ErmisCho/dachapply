---
id: TASK-381
title: 'Prepared documents: one adjustment applied to the documents I choose'
status: In Progress
assignee: []
created_date: '2026-11-16 14:15'
labels:
  - frontend
dependencies: []
priority: medium
ordinal: 382000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner, 2026-11-16: 'for the adjustment I need to choose which files to adjust'. The panel adjusted one document per Adjust box. Now each ready document's Adjust toggles it into one shared adjustment, which runs on every chosen document; the others stay unchanged.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Each ready, non-discarded document has an Adjust toggle (aria-pressed); one box lists the chosen documents with one instruction field
- [ ] #2 Adjust selected starts the existing per-document adjust for each chosen key, stops at the first failure and shows its error; unchosen documents are not touched
- [ ] #3 tsc and frontend tests pass, with a render test for the shared box; checked on localhost after merge
<!-- AC:END -->
