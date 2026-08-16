---
id: TASK-78
title: Track interview dates and surface upcoming interviews
status: Done
assignee:
  - '@claude'
created_date: '2026-08-16 00:43'
updated_date: '2026-08-16 13:55'
labels:
  - product
  - backend
  - frontend
dependencies: []
priority: medium
ordinal: 83000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`interview_stage` / `interview_total` are bare integers (backend/jobradar/models.py:60-61) — there is no date or time field anywhere on JobLead (models.py:43-67) for "interview on Thursday 10:00", and the dashboard shows only a count of jobs currently in interview status (views.py:719).

The single most time-critical event in a job search lives entirely outside the app that exists to manage it.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A job can hold its next interview date (with optional time and note), editable from job detail
- [x] #2 The dashboard surfaces upcoming interviews soonest-first, distinct from due follow-ups
- [x] #3 A past interview date does not linger as "upcoming"
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
One nullable DateTimeField covers it; per-round interview history is speculative until someone needs it (YAGNI). The dashboard panel pattern from due follow-ups (App.tsx:41-42) is reusable — pair with TASK-77's panel-linking work if scheduled together.

### Progress (2026-08-16) — backend landed in Wave 3, frontend is Wave 4

Left **In Progress**: both criteria name UI that does not exist yet, so nothing is checked.

Backend: `interview_at` (nullable DateTimeField) + `interview_note`, readable and writable through
the existing `fields='__all__'` serializer, so no serializer change was needed. `/api/stats/` gained
`upcoming_interviews` — already sorted soonest-first, already past-filtered, capped at 10, and kept
as a separate key from `jobs_needing_follow_up`. `interview_at` is deliberately *not* cleared on a
status change (unlike `interview_stage`/`interview_total`): a scheduled date is history worth
keeping, and the query filters by `>= now` anyway.

Verified by the coordinator against the live API with three seeded interviews (+2d, +9d, −1d):

    upcoming_interviews: Z-IntSoon 2026-08-18 "onsite round 2" , Z-IntLater 2026-08-25
    (the −1d row is absent)   jobs_needing_follow_up=1   interviews=3

so AC2's ordering and AC3's past-filtering already hold in the data.

### Closed 2026-08-16 — frontend half landed in Wave 4

AC1 measured as a full round trip on job detail, which is the only way to catch a timezone or
empty-value bug: typing `2026-09-03T10:00` into the `datetime-local` field and saving stored
`"2026-09-03T10:00:00+02:00"` — the correct Vienna offset, not a UTC-shifted hour — and reloading
the page put `2026-09-03T10:00` back in the input. Clearing the field and saving stored `null`,
**not** `""`, which is the failure that would otherwise sit silently in the database until something
tried to parse it. The note round-tripped as `"second round, onsite"` and is capped at the model's
250 characters.

AC2 measured by comparing the rendered panel against the API response it claims to display:

    API  : ["Z-IntSoon @ 2026-08-18T10:52Z", "Z-IntLater @ 2026-08-25T10:52Z"]
    panel: "Tue, Aug 18, 12:52 PM | Z-IntSoon — probe | onsite round 2 |
            Tue, Aug 25, 12:52 PM | Z-IntLater — probe"

Same rows, same order, same count — the panel maps and does not re-sort or re-filter, so the
backend's ordering guarantee is not quietly re-implemented on the client. It is a separate panel
from "Due follow-ups" (which still renders its own scalar `1`), satisfying AC2's "distinct from due
follow-ups" literally rather than by merging both into one list.

AC3 verified end to end: the seeded interview dated yesterday is absent from the API response *and*
from the panel.

Accessibility held: axe reports **0 violations** on `/jobs/2` after the page gained three inputs.
<!-- SECTION:NOTES:END -->
