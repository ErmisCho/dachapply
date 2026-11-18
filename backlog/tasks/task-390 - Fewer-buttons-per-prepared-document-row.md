---
id: TASK-390
title: Fewer buttons per prepared-document row
status: To Do
assignee: []
created_date: '2026-11-18 22:38'
labels: []
dependencies: []
priority: high
ordinal: 391000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Remove redundant per-variant controls: Keep (selecting already keeps) and the per-variant Copy TeX (package and TexPicker copy remain). Evidence: adjustments.jsonl 2026-10-21..11-18, 130 Adjusts over 34 jobs (median 3 ready Adjusts/job); audits in jobs/6526c3ef/tmp (optimization-audit.md, ux-audit.md). Owner approved 2026-11-18.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Variant rows no longer render Keep or Copy TeX; Preview PDF, Download, Discard/Restore, Adjust remain
- [ ] #2 Selecting a variant into the final package still marks it kept (existing behaviour verified by test)
- [ ] #3 npm test and tsc green
<!-- AC:END -->
