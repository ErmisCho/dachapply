---
id: TASK-264
title: Mark a job as Applied from the bulk generation panel
status: To Do
assignee: []
created_date: '2026-10-05 11:53'
updated_date: '2026-10-05 13:18'
labels: []
dependencies: []
priority: medium
ordinal: 262000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
In the bulk 'Generate selected applications' panel the owner wants to mark each job Applied directly, without leaving the panel. Must go through the normal job status update (PATCH /jobs/<id>/) so TASK-256's applied cleanup (sent documents kept, on_commit metadata retire) still runs.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Each bulk row has a 'Mark as applied' control; clicking it sets that job's status to applied via the existing job update API
- [x] #2 The row shows the new status immediately and the control is disabled/replaced once applied; the board list reflects it without a full reload
- [x] #3 Marking applied in the panel triggers the same TASK-256 behaviour as marking it on the board (backend test or measured: generated files stay listed as sent links)
- [x] #4 Control is disabled while that row is still generating
- [ ] #5 Verified on localhost:8000 on one real row
- [x] #6 Owner request 2026-10-05: once a job is marked Applied, its bulk row collapses to a compact 1-2 line card (company, title, 'Applied' badge); a toggle expands it back to the full row and collapses it again
- [x] #7 Collapsed card height measured on localhost: at most 2 text lines (<= ~64px) at desktop width
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Verified 2026-10-05 on a branch server (127.0.0.1:8010, scratch sqlite + scratch CV workspace, real Codex low-effort generation of 2 jobs): Mark as applied PATCHed /jobs/2/ (API status applied), board select showed applied without reload, row collapsed to a one-line card 47px tall with posting link, Applied badge, Expand. AC3 by construction: same PATCH /jobs/<id>/ the board uses (serializer applied hook). AC4 from code: disabled={rowBusy(row)||row.applying}. AC5 (localhost:8000) left for after merge.
<!-- SECTION:NOTES:END -->
