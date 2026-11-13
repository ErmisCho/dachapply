---
id: TASK-376
title: Cancel a queued job and restart it later
status: To Do
assignee: []
created_date: '2026-11-13 14:53'
labels: []
dependencies: []
priority: medium
type: feature
ordinal: 378000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The owner can cancel a job's pipeline or document work in the queue and restart it later, even after it was cancelled, without losing the job's posting text, requirements or already finished documents.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Running analyses and running/queued documents offer Cancel; cancellation stops the model call and shows the row under Failed/cancelled.
- [ ] #2 A cancelled job or document offers Restart at any later time (also after a server restart) and resumes from the step that was cancelled, reusing finished results.
- [ ] #3 Restart re-checks the daily limits and the job's current state (e.g. a changed posting) before starting.
- [ ] #4 Tests cover cancel and later restart for analysis and document rows, including after a restart of the server; browser-verified on the queue page.
<!-- AC:END -->
