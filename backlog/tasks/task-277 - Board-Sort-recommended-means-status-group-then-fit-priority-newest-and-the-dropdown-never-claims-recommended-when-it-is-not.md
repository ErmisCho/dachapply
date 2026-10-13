---
id: TASK-277
title: 'Board: honest Sort recommended - status group, fit, priority, newest'
status: Done
assignee: []
created_date: '2026-10-12 11:29'
updated_date: '2026-10-13 07:52'
labels:
  - board
  - bug
dependencies: []
priority: high
ordinal: 274000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner request 2026-10-12: 'the job listings that are new and are highest fit and priority should be at the top'. Owner's screenshot: dropdown reads 'Sort: recommended' while the board is actually sorted by header clicks (-fit_score,priority, persisted in localStorage dachapply_filters), so New jobs are mixed with Interview/Ready rows and two unscored rows (fit '—') sit above an 84% New job. Cause: f.ordering matches no <option>, so the browser shows the first option; picking 'recommended' then fires no change, so the owner cannot get back to the recommended order from the dropdown. Owner chose (AUQ): 'Recommended = New + fit + prio' and 'Honest sort label'; NOT the general unscored-last fix for other sorts and NOT a separate urgency change; then answered that inside a group urgency must NOT reorder rows (deadline / stale stay visible as badges only).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 With Sort: recommended, the board returns status groups in the owner's status order (TASK-267; New first by default) and within each group: highest fit score first, then priority high>medium>low, then newest created_at; measured against /api/jobs/ on a dataset that includes ties on fit and on priority
- [x] #2 Within each group under Sort: recommended, jobs with no fit score come after every scored job of that group, on PostgreSQL as well as SQLite (a test pins the NULL placement rather than relying on the database default)
- [x] #3 Inside a group, an apply-by date within DEADLINE_SOON_DAYS or an unapplied job older than STALE_UNAPPLIED_DAYS no longer changes row order under Sort: recommended; the '7d left' / 'Stale lead' badges still render unchanged
- [x] #4 Choosing Sort: recommended from the dropdown takes effect in one action from every other sort state: a header-click sort, a preset, and an account-saved board_sort_keys sort - each measured by the request sent and the rows returned
- [x] #5 The dropdown never displays 'Sort: recommended' while a different ordering is in effect: a header-click or saved sort shows as a visible non-recommended choice naming it (consistent with the 'Sorted by:' text and the header arrows)
- [x] #6 After a page reload, the dropdown label, 'Sorted by:' text, header arrows and returned row order all agree, for recommended, a preset, and a header-click sort
- [x] #7 TASK-267 section headers still appear under Sort: recommended with correct counts, and do not appear under any other sort
- [x] #8 Other sorts (presets, header clicks, saved account sort) return exactly the same order as before this task; parse_board_ordering's allowlist still rejects -created_by__password
- [x] #9 Backend pytest and frontend npm test + tsc pass; verified on the owner's localhost: board loads with Sort: recommended showing New-first, fit-descending rows
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Contract: the frontend sends ?ordering=recommended for Sort: recommended. parse_board_ordering maps the token 'recommended' to DEFAULT_BOARD_ORDERING (an old backend already degrades an unknown key to the default, so it is safe). An empty/absent ordering keeps today's meaning (account-saved board_sort_keys, else the default).
Backend (views.py + tests): DEFAULT_BOARD_ORDERING = attention_rank, fit_score desc nulls last, priority_rank, -created_at (stale_rank dropped from ordering; still annotated for badges if used).
Frontend (App.tsx, appUtils.ts + tests): the dropdown shows a named 'Sort: custom/saved (...)' option whenever the active ordering is not a preset; recommended sends ordering=recommended; TASK-267 section headers also show under recommended.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-13 verified: merged #219. Owner localhost (f174fdd) after relaunch: Sort: recommended selected, 'Sorted by: recommended', no header arrows, first section NEW · 18 with fit 58/57/56/56/55/54; Stale lead badges render without reordering. Saved-sort state (#4) measured by frontend/backend tests, not in the browser.
<!-- SECTION:NOTES:END -->
