---
id: TASK-312
title: >-
  Documents are prepared automatically after analysis, in a queue the owner can
  see and manage
status: Done
assignee: []
created_date: '2026-10-18 22:36'
updated_date: '2026-10-22 13:44'
labels: []
dependencies: []
ordinal: 311000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner (2026-10-19): 'as soon as I add jobs and analyze them, the relevant documents are generated in a queue, and I can see also this queue, and manage it and see what is done exactly'. Today preparation (TASK-280.2) starts only when a job moves to To apply, and every variant of every job starts at once.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 When an evaluation recommending 'apply' or 'maybe' is stored through the import paths (import_jobs nested evaluation, import_evaluations, so also Evaluate with model) for a New, Reviewed or To apply job, preparation of that job starts after the commit as the importing CV owner; 'skip' starts nothing. The existing prepare() rules still apply (requirements analysis first, pending-text gate, existing generated files left alone)
- [x] #2 Prepared variants run through one FIFO queue with at most PREP_QUEUE_CONCURRENCY (setting, default 1) document tasks running at once across all jobs; manual Generate is not queued. Each variant records queued_at, started_at and finished_at
- [x] #3 After a server restart, variants left queued or running (no live task) are re-queued automatically in their queued_at order, by the serving process only (same guard as the local mailbox loop)
- [x] #4 GET /api/jobs/application-prep/queue/ lists every variant across the owner's jobs: job id, company, title, variant label, document, language, status (queued|running|ready|failed|cancelled), queue position, progress, eta, error, file names and the three timestamps; running first, then queued by position, then finished newest first
- [x] #5 POST /api/jobs/application-prep/queue/action/ with job_id, key and action cancel (queued or running; running stops its task), retry (failed or cancelled, goes to the end of the queue) or first (queued, moves to the front); invalid combinations answer 400
- [x] #6 A Queue page in the app (linked in the navigation with the number queued+running) shows running items with progress and time left, queued items with position and Move to front / Cancel, finished items with what was produced (document, language, files) and a link to the job's review, and failed or cancelled items with the reason and Retry; it updates live while anything is queued or running
- [x] #7 The board's preparation badges also show for New and Reviewed jobs
- [x] #8 Tests cover the trigger (apply/maybe vs skip), the concurrency limit, restart re-queue and each queue action, each failing when its logic is removed; vitest, tsc and backend suite pass
- [x] #9 Verified on localhost: importing an evaluation for a job puts its documents in the queue page, they run one at a time, and finished items show their files
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Verified 2026-10-22: documents are prepared automatically after apply/maybe analyses and the Queue lists running/queued/blocked/done items with Retry/Cancel/Move first/Continue anyway; used daily since (TASK-313..340 built on it).
<!-- SECTION:NOTES:END -->
