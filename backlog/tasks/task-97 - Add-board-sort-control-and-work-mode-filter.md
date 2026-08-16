---
id: TASK-97
title: Add board sort control and work-mode filter
status: Done
assignee:
  - '@claude'
created_date: '2026-08-16 00:43'
updated_date: '2026-08-16 13:55'
labels:
  - frontend
  - backend
  - ux
dependencies: []
priority: low
ordinal: 102000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Board ordering is a fixed server-side formula with no `ordering` query parameter (backend/jobradar/views.py:323-327, get_queryset at 299-328), so the user cannot sort by fit score, newest, or feedback due. And while the backend already accepts a `work_mode` filter (views.py:305), the filter bar never sends it — the frontend filter object holds only search/location/min_fit_score/priority/recommendation/status/company (App.tsx:98, verified by extracting every `f.*` access) — so remote-only filtering is impossible from the UI despite being implemented server-side.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The board can sort by fit score, newest, and feedback due, in addition to the default formula (which remains the default)
- [x] #2 A work-mode filter (remote/hybrid/onsite) exists in the filter bar and passes through to the existing backend parameter
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
work_mode is a select plus one key in the filter object — the backend half already exists. Sort needs a whitelisted `ordering` param on the viewset; do not expose arbitrary field ordering.

### Closing notes (2026-08-16)

Split across two agents in the same wave: the frontend shipped first and correctly reported AC1 as
**NOT MET**, because the backend had no `ordering` parameter and the control was inert. It did not
paper over the gap by sorting the fetched page client-side — which would have "worked" here, since
there is no pagination, and would have been the wrong place for it. The coordinator routed the exact
contract to the backend agent instead.

AC1: `BOARD_ORDERINGS` is a dict of three accepted keys; the query parameter is used as a **lookup
key and never as an argument to `order_by()`**. That distinction is the whole security point — passing
it through would let a client order by any related column (`?ordering=-created_by__password`) and
read values off the resulting row order. Verified against the live API:

    ordering=<absent>                 -> 14 rows: 8,9,2,10,4,3,14,13   (default formula)
    ordering=-created_at              -> 14 rows: 14,13,12,10,9,8,7,6
    ordering=-fit_score               -> 14 rows: 3,2,1,14,13,12,10,9
    ordering=feedback_due_date        -> 14 rows: 14,13,12,10,9,8,7,6  (nulls last)
    ordering=password                 -> 14 rows: 8,9,2,10,4,3,14,13   (default, unchanged)
    ordering=-created_by__password    -> 14 rows: 8,9,2,10,4,3,14,13   (default, unchanged)

Both injection attempts fall through to the default without erroring, and the **row count stays 14
in every case** — checked deliberately, because ordering by a related field next to the existing
`.distinct()` is a classic way to start emitting duplicate rows, and sqlite and production Postgres
do not always agree about it.

The default server-side formula remains the default, as AC1 requires; sorting is an opt-in override.

AC2 measured: selecting Remote and applying issues
`GET /api/jobs/?…&work_mode=remote&board=1` — the filter reaches the pre-existing backend parameter
rather than being applied client-side. The select carries `aria-label="Work mode"`, and the sort
select `aria-label="Sort board by"`, so neither reintroduces the unlabelled-control class TASK-87
just cleared.
<!-- SECTION:NOTES:END -->
