---
id: TASK-264
title: Mark a job as Applied from the bulk generation panel
status: To Do
assignee: []
created_date: '2026-10-05 11:53'
updated_date: '2026-10-05 12:01'
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
- [ ] #1 Each bulk row has a 'Mark as applied' control; clicking it sets that job's status to applied via the existing job update API
- [ ] #2 The row shows the new status immediately and the control is disabled/replaced once applied; the board list reflects it without a full reload
- [ ] #3 Marking applied in the panel triggers the same TASK-256 behaviour as marking it on the board (backend test or measured: generated files stay listed as sent links)
- [ ] #4 Control is disabled while that row is still generating
- [ ] #5 Verified on localhost:8000 on one real row
- [ ] #6 Owner request 2026-10-05: once a job is marked Applied, its bulk row collapses to a compact 1-2 line card (company, title, 'Applied' badge); a toggle expands it back to the full row and collapses it again
- [ ] #7 Collapsed card height measured on localhost: at most 2 text lines (<= ~64px) at desktop width
<!-- AC:END -->
