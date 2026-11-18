---
id: TASK-391
title: Disabled buttons explain why
status: To Do
assignee: []
created_date: '2026-11-18 22:39'
labels: []
dependencies: []
priority: high
ordinal: 392000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
'Select as final package', the per-variant Adjust, Readjust and Recompile show a title/tooltip with the reason when disabled. Evidence: adjustments.jsonl 2026-10-21..11-18, 130 Adjusts over 34 jobs (median 3 ready Adjusts/job); audits in jobs/6526c3ef/tmp (optimization-audit.md, ux-audit.md). Owner approved 2026-11-18.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Each of these buttons has a non-empty title when disabled naming the reason (busy, nothing changed, no document ticked, no instruction, adjusting)
- [ ] #2 Enabled buttons keep their current label and no misleading title
<!-- AC:END -->
