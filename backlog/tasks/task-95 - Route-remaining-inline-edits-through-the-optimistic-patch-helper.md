---
id: TASK-95
title: Route remaining inline edits through the optimistic patch helper
status: Done
assignee:
  - '@claude'
created_date: '2026-08-16 00:43'
updated_date: '2026-08-16 12:40'
labels:
  - frontend
  - performance
  - ux
dependencies: []
priority: low
ordinal: 100000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
TASK-16 made status edits optimistic, but three inline-edit paths still bypass its helper: the application-date input, the mobile last-update date, and the three feedback-due inputs all do a raw `api(PATCH)` followed by `load()` (frontend/src/App.tsx:98) — and `load()` refetches four endpoints (`/jobs/`, `/stats/`, `/jobs/?status=new`, `/auth/friend-requests/`) for a single date change, with the server re-sort jumping rows under the user's cursor.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The listed date edits update through the same optimistic path as status edits: no four-endpoint reload, no row jump
- [x] #2 A server failure still rolls back and reports exactly as TASK-16's status path does
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Follow-up to TASK-16 — the helper exists; these call sites predate it. Route them through it rather than duplicating its rollback logic.

### Closing notes (2026-08-16)

**The ticket undercounted the call sites: there are 8, not 3.** Enumerated by character offset
(line-based grep is useless here — the Dashboard line is ~53k characters): three `feedback_due_date`
writers and one `status_date` writer in the mobile popover/row, and the same four again in the
desktop `isEdit` else-branch. All 8 now call `patchJob`. A re-scan finds **zero** remaining
`api('/jobs/'+j.id+'/',{method:'PATCH'` in `Dashboard`; the surviving `load()` calls are the
legitimate ones (initial mount, bulk apply, delete, prompt-import success). Siblings that were
already optimistic — both `last_update_date` inputs, `interview_stage`/`interview_total`, and both
status selects — were left alone. Fixing only the three the ticket named would have left five
identical bugs in place.

AC1 measured in a browser with the network log open. One application-date edit produced exactly:

    PATCH /api/jobs/3/

and nothing else — no `GET /jobs/`, no `/stats/`, no `/jobs/?status=new`, no
`/auth/friend-requests/`. Row order before and after the edit was identical, so the server re-sort
no longer moves the row under the cursor.

**AC2 turned up a real defect and it was fixed rather than inherited.** Routing through `patchJob`
made these edits behave *exactly* like the status path — which, measured, reported nothing at all:
`patchJob`'s `catch` did `setErr(e); load()`, and `load()` opens with `setErr(null)`, so the error
was set and wiped in the same tick. Polling the alert region every 60ms during a forced failure on
the pre-existing status select caught no message at any point, confirming this was TASK-16's bug and
not something this task introduced. The fix is a one-token reorder — `catch(e){load();setErr(e)}` —
because `load()` clears the error synchronously, so setting it afterwards sticks. That repairs all
nine call sites at once, including the status path TASK-16 shipped.

Re-measured after the fix, with the PATCH forced to 500:

    date edit   -> "! forced patch failure"
    status edit -> "! forced patch failure"   (the pre-existing path, now also reporting)

Rollback is restore-by-refetch, not a snapshot revert — that is what TASK-16 shipped and this task
deliberately does not change it.
<!-- SECTION:NOTES:END -->
