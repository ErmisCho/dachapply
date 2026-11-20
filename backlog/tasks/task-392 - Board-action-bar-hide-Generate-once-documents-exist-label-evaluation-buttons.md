---
id: TASK-392
title: 'Board action bar: hide Generate once documents exist, label evaluation buttons'
status: Done
assignee: []
created_date: '2026-11-18 22:39'
updated_date: '2026-11-20 08:07'
labels: []
dependencies: []
priority: high
ordinal: 393000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Job board/job page action bar: the Generate action is hidden once prepared variants exist (Adjust/Prepare remain), and the two evaluation buttons get distinct labels saying what each does. Evidence: adjustments.jsonl 2026-10-21..11-18, 130 Adjusts over 34 jobs (median 3 ready Adjusts/job); audits in jobs/6526c3ef/tmp (optimization-audit.md, ux-audit.md). Owner approved 2026-11-18.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 With prepared variants present, the Generate button is not rendered; without variants it is
- [x] #2 The two evaluation buttons have distinct visible labels or titles that name their difference
- [x] #3 npm test and tsc green
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
PR #434: board toolbar hides single-job Generate when the selected job has ready prepared documents (existing prep poll). Verified on localhost 2026-11-20 (bundle index-SYQWfm8p.js): job 2086 selected -> Generate shown; job 2024 (prepared CV) selected -> hidden.
<!-- SECTION:NOTES:END -->
