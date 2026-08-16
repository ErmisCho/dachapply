---
id: TASK-79
title: Add an apply-by deadline to job leads
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
ordinal: 84000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The only date pressure the app models is post-application: `feedback_due_date` (backend/jobradar/models.py:63) applies after submitting. JobLead (models.py:43-67) has no deadline or apply-by field, so a lead whose posting closes on Friday looks identical to an evergreen one — to_apply jobs die silently while the user works the board top-down.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A job can hold an apply-by date, editable from the add form and job detail
- [x] #2 Approaching and past deadlines are visible on new/reviewed/to_apply rows on the board (badge and/or ranking boost)
- [x] #3 A past-deadline unapplied job is visually distinct from an evergreen one
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
One nullable DateField plus a badge. For ranking, extend the existing stale_rank Case (views.py:324) rather than inventing a second urgency system — TASK-96 touches the same expression, so schedule them together or sequence them.

### Progress (2026-08-16) — backend landed in Wave 3, frontend is Wave 4

Left **In Progress**: AC1 needs form inputs and AC2/AC3 need a badge, none of which exist yet.

Backend: `apply_by` (nullable DateField), readable/writable through the existing serializer. The
ranking half is done and, as instructed, it extends the single existing `stale_rank` `Case` rather
than adding a second urgency annotation — the expression now returns −1 (surface), 0 (normal),
1 (sink). `DEADLINE_SOON_DAYS = 7` lives on the model beside the other thresholds and is published
to the frontend at `/api/auth/me/ → board_thresholds`.

Coordinator-verified against the live board with seeded rows:

    0. Z-Overdue    new       apply_by=2026-08-13   <- past deadline, surfaced
    1. Z-DueSoon    to_apply  apply_by=2026-08-19   <- within 7 days, surfaced
    3. Z-Normal     new       apply_by=None
   12. Z-Forgotten  to_apply  created 45d ago       <- sunk (TASK-96)

Wave 4 owes: an `apply_by` input on the add form and job detail, and a board badge. Note the
backend ranks *past* and *approaching* identically at −1, so AC3's "past-deadline is visually
distinct from evergreen" is entirely a frontend styling decision — the ordering will not make that
distinction for you.

### Closed 2026-08-16 — frontend half landed in Wave 4

AC1: `apply_by` is editable in both places the criterion names — "Apply by (optional)" on the add
form and "Apply by" on job detail, both real `<label>`s rather than placeholder-only inputs. It was
deliberately **not** added to `/public-submit`: that route posts through `PublicSubmissionSerializer`,
an explicit seven-field whitelist with no `apply_by`, so an input there would have silently
discarded whatever the user typed. Worth recording, because "the field is on every form" would have
looked more complete and been worse.

AC2/AC3 measured on the live board with seeded rows, which is what proves the three-way split the
backend ordering cannot express (it ranks past and approaching identically at -1):

    Z-Overdue  (apply_by 3 days ago)     red    "Deadline passed 3d ago"
    Z-DueSoon  (apply_by in 3 days)      yellow "Apply in 3d"
    Z-Normal   (no apply_by)             no badge at all

So past is distinguishable from approaching, and both from evergreen. The same three badges render
in the mobile card layout at 390px, with `document.scrollWidth == window.innerWidth` (390 == 390),
so the added badges do not make the page scroll sideways.

Badges are gated on `board_thresholds.unapplied_statuses`, matching the backend's `stale_rank` gate
rather than re-deciding which statuses count.
<!-- SECTION:NOTES:END -->
