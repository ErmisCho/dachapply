---
id: TASK-393
title: Bake repeated spacing fixes into stored CV templates (dry-run command)
status: To Do
assignee: []
created_date: '2026-11-18 22:39'
labels: []
dependencies: []
priority: high
ordinal: 394000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Management command applies the owner's most repeated spacing OLD/NEW pairs (resumeItemListEnd vspace -5pt to the owner's value, end tabular* vspace -7pt to 0pt) to stored CV templates. Dry-run by default; --apply writes. Owner approved dry-run first 2026-11-18. Evidence: adjustments.jsonl 2026-10-21..11-18, 130 Adjusts over 34 jobs (median 3 ready Adjusts/job); audits in jobs/6526c3ef/tmp (optimization-audit.md, ux-audit.md). Owner approved 2026-11-18.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Dry-run prints, per stored CV template, each pair's match count and a unified diff; writes nothing
- [ ] #2 --apply changes only the matched spans (byte-local) and only templates where every pair matches exactly once; others are reported and skipped
- [ ] #3 Tests on a fixture template cover dry-run no-write, apply, and a skipped template
- [ ] #4 The owner sees the dry-run output against the real database before --apply is run
<!-- AC:END -->
