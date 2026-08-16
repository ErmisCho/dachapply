---
id: TASK-75
title: Add offer, accepted and withdrawn terminal statuses
status: Done
assignee:
  - '@claude'
created_date: '2026-08-16 00:43'
updated_date: '2026-08-16 12:40'
labels:
  - product
  - backend
  - frontend
dependencies: []
priority: high
ordinal: 80000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The status pipeline is new → reviewed → to_apply → applied → interview → rejected/skipped/archived (backend/jobradar/models.py:45, mirrored in frontend/src/App.tsx:9 — verified 2026-08-16, grep for "offer" across backend has zero product hits).

The happy end of the funnel is unrepresentable: an offer has no home, an accepted offer has no home, and a search the user chose to end (withdrawn) is indistinguishable from a rejection. Without terminal success states the app can never answer "what worked" (see TASK-85).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 offer, accepted, and withdrawn exist end to end: model choices, board status filter, status editor, and badges
- [x] #2 Existing status machinery treats them sensibly: offer is a dated status (frontend datedStatuses, App.tsx:10); accepted and withdrawn are terminal and never flagged stale (stale_rank at views.py:324, isStaleStatus at App.tsx:33)
- [x] #3 Stats include the new statuses without breaking existing counts
- [x] #4 Backend tests cover a job moving applied → interview → offer → accepted
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Two mirrored lists to extend (models.py:45, App.tsx:9) plus the small status-adjacent sets named in AC2. No migration beyond the choices change — status is a CharField.

### Closed 2026-08-16 — backend half in Wave 1, frontend half in Wave 2

Held **In Progress** through Wave 1 on purpose: no criterion here was satisfiable until the mirrored
frontend lists landed, so nothing was checked on the backend half alone.

Backend, done and tested:
- `STATUSES` gained `offer`, `accepted`, `withdrawn`; migration `0021` carries the choices change.
- `DATED_STATUSES = ['applied','interview','offer']` on the model now backs `stale_rank`
  (`views.py`) and the five status-transition branches in `serializers.py` that previously each
  hard-coded `['applied','interview']`.
- `status_rank` groups `offer` with `interview` so an offer sorts as an active row.
- Stats gained `offers`, `accepted`, `withdrawn` counts.
- `test_terminal_statuses_never_go_stale_but_an_old_offer_does` discriminates in both directions: it
  creates three 30-day-old jobs and asserts the offer sorts last (stale) while the equally old
  `accepted` and `withdrawn` sort ahead of it — so it would fail if `offer` were undated *or* if the
  terminal statuses were treated as stale. `test_status_walk_applied_interview_offer_accepted`
  covers AC4's walk.

Frontend half (Wave 2):
- `statuses` (App.tsx:10) now reads
  `['new','reviewed','to_apply','applied','interview','offer','accepted','rejected','withdrawn','skipped','archived']`
  — byte-for-byte the order of `models.py` `STATUSES`, checked by diffing the two lists rather than
  by eye. That one const feeds every consumer: the board status-filter dropdown, the default
  not-archived filter, the bulk-edit select, the mobile per-row select, both desktop per-row select
  branches, and the add/edit form select.
- `statusTone` gained `offer:'green'`, `accepted:'green'`, `withdrawn:'slate'`.
- `datedStatuses` gained `offer`; `lastUpdateStatuses` is now exactly backend
  `JobLead.DATED_STATUSES`, and `isStaleStatus` derives from it instead of carrying its own
  hardcoded `applied||interview` — one more mirrored literal removed rather than added.

AC2 measured against the live API rather than argued from the code. Three jobs were aged to a
30-day-old `status_date`, one in each new status, and the board order was read back:

    2:new , 4:new , 3:offer , 1:applied , 7:withdrawn , 6:accepted , 5:offer

The aged **offer** (id 5) sorts last — `stale_rank=1`. The equally aged **withdrawn** (7) and
**accepted** (6) sort ahead of it, so they are not stale. The check discriminates in both
directions: were `offer` not a dated status it would sort *earlier* (status_rank 3 beats 5), and
were the terminal statuses stale they would sit beside it at the end. On the frontend the same
guarantee is structural — `isStaleStatus` tests membership of `['applied','interview','offer']`, so
`accepted` and `withdrawn` cannot reach it.

AC3: `/stats/` gained `offers`, `accepted`, `withdrawn`; the existing counts are unchanged and the
full suite still passes.

Known cosmetic limitation, not a defect: `interview`, `offer` and `accepted` all render green
because `index.css` defines only six badge tones. The badge *text* differs, so no information is
carried by colour alone (the one true colour-only case in the app is skill badges — TASK-87).
Add a seventh tone in `index.css` if the terminal win should read differently at a glance.

Also left alone deliberately: `feedbackDays` still tests `applied||interview`, because its output is
only ever rendered behind an `interview` gate — adding `offer` there would be dead code, and giving
offers a feedback-due column is a product decision, not a mirroring fix.
<!-- SECTION:NOTES:END -->
