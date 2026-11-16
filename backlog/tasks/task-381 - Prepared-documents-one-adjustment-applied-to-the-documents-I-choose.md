---
id: TASK-381
title: 'Prepared documents: one adjustment applied to the documents I choose'
status: Done
assignee: []
created_date: '2026-11-16 14:15'
updated_date: '2026-11-16 16:16'
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
- [x] #1 Each ready, non-discarded document has an Adjust toggle (aria-pressed); one box lists the chosen documents with one instruction field
- [x] #2 tsc and frontend tests pass, with a render test for the shared box; checked on localhost after merge
- [x] #3 Adjust these N starts the existing per-document adjust for each chosen key in parallel; a refused start stops the rest and shows its error; a failure during generation shows on that document; unchosen documents are not touched
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Codex review: adjustments run in the background, so 'stops at the first failure' covers a refused start only; a failure during generation shows as that document's adjust_error. Kept parallel (each adjust takes minutes); AC2 worded accordingly.

Verified on localhost 2026-11-16 (7640567, logged in): job 2063 shows per-document Adjust toggles; choosing one shows "Adjust only this", both shows "Adjust these 2" and the shared box; job 1897 (CV only, status new) shows Prepare letter; the panel shows the new letter rule. No generation was started for the check. Adjust these N was not clicked live (it starts paid generations); covered by the merged code and tests.
<!-- SECTION:NOTES:END -->
