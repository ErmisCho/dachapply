---
id: TASK-187
title: The board list runs one auth_user query per row
status: In Progress
assignee:
  - '@pi'
created_date: ''
updated_date: '2026-08-28 13:00'
labels:
  - backend
  - performance
dependencies: []
priority: medium
ordinal: 187000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found on 2026-08-24 by the agent implementing TASK-178's backend half, while proving its own field
added no N+1. It reported the defect rather than folding an unrelated fix into its diff, which was
the right call — and the number is measured, not estimated.

Serializing the board costs **69 `auth_user` SELECTs for 69 rows**:

```
queries by leading table:  auth_user 69 | jobradar_userprofile 1 | jobradar_joblead 1 | jobradar_jobevaluation 1
```

The source is `JobLeadSerializer`'s `get_created_by_username`, `get_created_by_email`,
`get_submitted_for_username` and `get_submitted_for_email` — four `SerializerMethodField`s that each
walk a foreign key the queryset never joined.

`select_related('created_by','submitted_for')` in `JobLeadViewSet.get_queryset()` would collapse
roughly 72 queries to 3. It is one line, but it changes the board query's shape, and it was found
mid-wave while a frontend agent was verifying against that exact endpoint — so it was deliberately
left alone rather than landed unmeasured.

This is the same family as the 36s Mailbox page (commit `4de24d0`) and the per-row request TASK-91
was filed to avoid. It has presumably been there since `created_by`/`submitted_for` were added.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The board list issues a constant number of queries regardless of row count, proven by a test that fails on the current code
- [x] #2 Measured before and after against a real board: query count and wall-clock, stated as numbers
- [x] #3 TASK-184's ownership scoping is unchanged — `select_related` must not alter which rows are returned, only how they are fetched
- [x] #4 TASK-178's `note_preview` subquery and TASK-126's `has_mailbox_history` annotation both still resolve in the single list query
- [x] #5 Backend suite green
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Re-measure the recovered list queryset and verify every relation accessed by the board serializer. 2. Preserve owner scoping while joining creator/submission users and prove query count is row-count invariant. 3. Record real-board query/wall-clock measurements and run the backend suite.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
TASK-178's query-count test deliberately compares notes-absent vs notes-present **at a fixed row
count** rather than scaling rows, precisely because a rows-scaling assertion would measure this
defect instead of that field. Once this is fixed, that test can be strengthened to scale rows — which
is the better test, and is worth doing as part of this task.

Do not stop at `select_related`. Confirm afterwards that no other `SerializerMethodField` on the list
path walks an unjoined relation; the measurement above only names the ones that dominate.

Session Orchestrator deep session resumed the abandoned implementation from snapshot f85ca993 into isolated branch session-rest-backlog; prior output is treated as untrusted until reverified.

Wave 1 recovery validation: focused backend slice passed; recovered row-scaling test reports a constant count with no auth_user SELECTs. Full and pre-fix mutation checks remain for Quality.

Wave 2: mutation verification proved the regression test fails pre-fix at 17 vs 35 queries and passes with select_related; impacted backend files passed 681 tests.

Wave 4 production measurement: 69 rows now cost 3 list-owned queries, 18 whole-request queries, 0 auth_user SELECTs, and 1370.3 ms in-process; browser board response measured 1521.3 ms versus 72 queries/3513 ms before. Temporary pre-fix mutation reproduced 17 queries for 3 rows versus 35 for 12. Ownership/annotation tests and all 1014 backend tests passed. Asian Dad: PERFECT (rubric created late and self-graded, disclosed).
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Joined created_by/submitted_for once in the board queryset, eliminating row-scaled auth lookups without changing accessible rows or note/mail annotations. The regression test fails pre-fix, production now uses three list queries with no auth_user SELECT, and the full backend suite passes.
<!-- SECTION:FINAL_SUMMARY:END -->
