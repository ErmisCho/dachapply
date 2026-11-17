---
id: TASK-383
title: Exact OLD/NEW route replaces every copy of a repeated OLD
status: Done
assignee: []
created_date: '2026-11-17 09:31'
updated_date: '2026-11-17 09:51'
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
- [x] #1 An OLD occurring 2+ times in the ticked documents is replaced everywhere by exact_revision_plan; OLD with a '...' wildcard still requires a unique match
- [x] #2 Re-running the same instruction afterwards returns {} (no change), not None
- [x] #3 Job 2086's logged instruction routes 'exact' on a copy of its real CV (dry run)
- [x] #4 New test fails on the old code, passes on the fix; backend suite green
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Merged in #423 (4c55ec4) with Codex P1/P2 fixes (ticked copies win; refuse when NEW contains OLD). Red/green done; job 2086 dry run on rebuilt pre-edit CV: 6 edits, no AI, rerun no-op. Runtime updated to 4c55ec4, health 200, resumed.
<!-- SECTION:NOTES:END -->
