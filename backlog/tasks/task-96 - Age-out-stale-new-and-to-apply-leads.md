---
id: TASK-96
title: Age out stale new and to_apply leads
status: Done
assignee:
  - '@claude'
created_date: '2026-08-16 00:43'
updated_date: '2026-08-16 13:55'
labels:
  - product
  - frontend
  - backend
dependencies: []
priority: low
ordinal: 101000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Staleness handling covers only applied/interview older than 21 days (backend/jobradar/views.py:324 `stale_rank`, frontend/src/App.tsx:33 `isStaleStatus`). A lead sitting in new/reviewed/to_apply for two months looks identical to one added yesterday, even though job postings typically expire within weeks — dead leads accumulate and bury live ones.

Link-liveness checking (fetching each URL to detect expired postings) was considered and deliberately skipped: `original_source_text` already preserves the posting content, and age is the honest cheap signal.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 new/reviewed/to_apply leads older than a documented threshold (e.g. 30 days since creation) are visibly marked stale on the board
- [x] #2 A one-click archive affordance exists for stale leads (per-row or bulk)
- [x] #3 The threshold is consistent between backend ordering and the frontend badge, stated in one place
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Extend the existing stale_rank Case and isStaleStatus rather than adding a parallel mechanism. TASK-79 (apply-by deadline) touches the same ranking expression — sequence the two or hand them to one agent.

### Progress (2026-08-16) — backend landed in Wave 3, frontend is Wave 4

Left **In Progress**: AC1 asks for a visible mark and AC3 is only closed once the frontend stops
carrying its own copy of the number.

Backend: the same single `stale_rank` `Case` now also sinks `new`/`reviewed`/`to_apply` leads older
than the threshold — no parallel mechanism, and no link-liveness fetching (explicitly rejected in
the description, and still rejected). Coordinator-verified on the live board: a `to_apply` lead
created 45 days ago sorts **last** (position 12 of 13), behind both a fresh lead and an evergreen
one.

Threshold, stated in one place as AC3 requires — `JobLead` in `models.py`:

    STALE_UNAPPLIED_DAYS = 30   (the AC's own suggested figure; postings typically expire in 4-6
                                 weeks, so 30 days is past "probably still live" without flagging
                                 a lead added three weeks ago)
    STALE_APPLIED_DAYS   = 21   (the pre-existing magic 21 in views.py, now named rather than changed)
    DEADLINE_SOON_DAYS   = 7

Published to the client at `GET /api/auth/me/ → board_thresholds`, verified returning:

    {"stale_applied_days":21,"stale_unapplied_days":30,"deadline_soon_days":7,
     "unapplied_statuses":["new","reviewed","to_apply"],
     "dated_statuses":["applied","interview","offer"]}

`/auth/me/` rather than `/stats/` because the board already has that payload and never fetches
`/stats/`.

**AC2 needs no new code and none was written.** A one-click archive already exists end to end:
`PATCH /api/jobs/<id>/ {"status":"archived"}`, with both the bulk "Archive selected" and the
per-row archive already wired to it on the frontend. Recording that rather than inventing an
endpoint to have something to show.

Wave 4 owes: the stale badge for unapplied leads, and — this is what actually closes AC3 — deleting
the hardcoded `21` from **both** `isStaleStatus` and `feedbackDays` in App.tsx and reading
`board_thresholds` instead. Note `me()` reads a `localStorage` copy that for an existing session
predates this change and has no `board_thresholds`, so the read needs a default or the badge
silently vanishes for already-logged-in users until their next refetch.

### Closed 2026-08-16 — frontend half landed in Wave 4

AC1 measured: the seeded `to_apply` lead created 45 days ago renders a slate **"Stale lead"** badge
and the row greys, reusing the existing stale tint rather than introducing a second one. Confirmed
in both the desktop table and the mobile card layout.

AC3 — the criterion this task actually turns on — is now closed at both ends. No hardcoded threshold
remains in `App.tsx`: a scan for the literal `21` finds exactly two hits and neither is a threshold
(the word inside an explanatory comment, and `S21.75` inside an SVG path). Both `isStaleStatus` and
`feedbackDays` read `boardThresholds()`.

**The cached-payload trap was handled properly and I verified it.** `me()` reads a `localStorage`
copy that, for anyone already logged in when this deploys, predates the change and has no
`board_thresholds` — the obvious "fix" is a numeric default like `{stale_applied_days: 21}`, which
would have recreated the exact duplication this AC exists to delete. Instead the reader prefers this
page load's live `/auth/me/` response and every numeric read tolerates `undefined` explicitly, so a
missing key degrades to "no badge" rather than `NaN d left`.

Measured with a deliberately pre-deploy cached user (a `dachapply_user` object with
`board_thresholds` removed): badges rendered **identically** to the healthy case —
`Z-Overdue` red, `Z-DueSoon` yellow, `Z-Forgotten` slate. That was the single most likely way for
this to look correct locally and be broken for the owner, so it is the one worth having measured.

AC2 needed no new code and none was written: the per-row status select and the bulk "Archive
selected" both already reach `PATCH {status:'archived'}` on every row.
<!-- SECTION:NOTES:END -->
