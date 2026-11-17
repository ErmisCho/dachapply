---
id: TASK-383
title: Exact OLD/NEW route replaces every copy of a repeated OLD
status: To Do
assignee: []
created_date: '2026-11-17 09:31'
labels: []
dependencies: []
priority: medium
ordinal: 384000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner decision 2026-11-17: when an OLD block occurs more than once in the ticked documents, replace every copy instead of sending the whole request to the cloud model. Job 2086: '\end{tabular*}\vspace{-7pt}' occurs twice in the CV.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 An OLD occurring 2+ times in the ticked documents is replaced everywhere by exact_revision_plan; OLD with a '...' wildcard still requires a unique match
- [ ] #2 Re-running the same instruction afterwards returns {} (no change), not None
- [ ] #3 Job 2086's logged instruction routes 'exact' on a copy of its real CV (dry run)
- [ ] #4 New test fails on the old code, passes on the fix; backend suite green
<!-- AC:END -->
