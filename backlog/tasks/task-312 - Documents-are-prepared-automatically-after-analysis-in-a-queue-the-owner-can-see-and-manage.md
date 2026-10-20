---
id: TASK-312
title: >-
  Documents are prepared automatically after analysis, in a queue the owner can
  see and manage
status: In Progress
assignee: []
created_date: '2026-10-18 22:36'
updated_date: '2026-10-20 17:00'
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
2026-10-19: #295 merged; queue page live on localhost (PORR's ready CV listed with files + Review). AC9 open: a live import-to-queue run on a real job needs the owner's OK (real-data write).

AC9 verified 2026-10-19: evaluate-with-model on 5 new jobs (owner OK) -> 4 maybe; job 1846 was queued, ran alone (concurrency 1) and finished with CV DE .tex+.pdf shown under Done. The 3 link-only jobs were refused by the posting-text gate and not shown -> TASK-313; placeholder names in filenames -> TASK-314.

2026-10-20 AC6 measured in headless Chrome against a scratch server (origin/main c44e969, scratch sqlite + CV workspace, provider faked at generate_cv_package): nav 'Queue 4'->1 live without reload; Running '35% · about 2 min left'; Queued #1-#3 with Move to front (Echo #3->#1) and Cancel (Beta -> Cancelled), API agreed; Done shows document, language, files and Review -> /jobs/<id>; Failed shows reason + Retry (Delta -> queued #3, then ran). One running at a time throughout. Poll 3.0 s while active, 30.0 s idle (nav count). AC8: 25/25 mutations of trigger, skip, concurrency, restart re-queue, cancel/retry/first and the 400 guards make tests in test_application_prep_queue.py fail (2 re-run by the coordinator); backend 1788 passed, vitest 463 passed, tsc clean.
<!-- SECTION:NOTES:END -->
