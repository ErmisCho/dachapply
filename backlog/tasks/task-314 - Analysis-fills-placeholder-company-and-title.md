---
id: TASK-314
title: Analysis fills placeholder company and title
status: Done
assignee: []
created_date: '2026-10-19 14:38'
updated_date: '2026-10-19 16:55'
labels:
  - backend
dependencies: []
priority: medium
ordinal: 314000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Live run 2026-10-19: link-only jobs keep 'Unknown company' / 'Untitled role N' after analysis although the evaluation carries company and title, so the board and the generated CV filename (…CV-Unknown-Company-Untitled-Role-2.pdf) use placeholders. Owner chose: fill them automatically when they are still placeholders.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 When an evaluation is saved and the job's company is empty or 'Unknown company', a real company name from the evaluation replaces it
- [x] #2 When the job's title is empty or starts with 'Untitled role', a real title from the evaluation replaces it
- [x] #3 A company or title the owner set (not a placeholder) is never overwritten; placeholder or URL values in the evaluation are never written
- [x] #4 Applies to both evaluation paths (paste import and evaluate-with-model) and happens before documents are prepared, so generated filenames use the real names
- [x] #5 Tests cover fill, keep-owner-value and placeholder-in-evaluation; full backend suite passes
- [x] #6 Verified on localhost on a job that still has placeholder names
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Verified on localhost 2026-10-19 (PR #298): re-analysing job 1875 renamed 'Unknown company / Untitled role 1' to 'Senacor / AI-Native Software Engineer'.
<!-- SECTION:NOTES:END -->
