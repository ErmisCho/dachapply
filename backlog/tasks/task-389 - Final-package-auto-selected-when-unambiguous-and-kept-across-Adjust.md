---
id: TASK-389
title: Final package auto-selected when unambiguous and kept across Adjust
status: To Do
assignee: []
created_date: '2026-11-18 22:38'
labels: []
dependencies: []
priority: high
ordinal: 390000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Prepared documents: when exactly one usable CV and one usable letter set (one language) exist and nothing is selected, select them as the final package automatically; an Adjust of a selected variant keeps the selection instead of clearing it. Evidence: adjustments.jsonl 2026-10-21..11-18, 130 Adjusts over 34 jobs (median 3 ready Adjusts/job); audits in jobs/6526c3ef/tmp (optimization-audit.md, ux-audit.md). Owner approved 2026-11-18.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 With one usable CV + one usable letter of the same language and no selection, the job ends with that selection without a click (backend test on the prep state)
- [ ] #2 With two candidate CVs or mixed languages, nothing is auto-selected
- [ ] #3 After a successful Adjust of a selected variant the selection is still set (backend test); other invalidations (posting changed, files missing) still clear it
<!-- AC:END -->
