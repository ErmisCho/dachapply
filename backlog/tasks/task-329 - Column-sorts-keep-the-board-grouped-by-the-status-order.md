---
id: TASK-329
title: Column sorts keep the board grouped by the status order
status: To Do
assignee: []
created_date: '2026-10-21 13:32'
labels:
  - backend frontend
dependencies: []
priority: medium
ordinal: 329000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner 2026-10-21 (screenshot of the Statuses order New, Interview, Reviewed, To apply, Ready to submit, Applied, ...): 'if applied is lower than to apply or new, then why do I see just applied at first in this table?' Measured: the board was on 'Sort: custom - Fit score (desc), then Priority'; parse_board_ordering only uses attention_rank (the saved status order, TASK-267) for the Recommended sort, so a column sort ignores it. Owner chose: always group by status, the column sort applies within each group. Unscored jobs stay first on fit desc (owner: keep as is).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Any column sort that does not include Status is applied within the saved status order groups (attention_rank first)
- [ ] #2 Sorting by the Status column itself is unchanged (pipeline order, both directions)
- [ ] #3 Recommended sort is unchanged
- [ ] #4 The Sorted by readout says the status order comes first for such sorts
- [ ] #5 Live: with Fit score sorting, New jobs come before Applied ones on the board
<!-- AC:END -->
