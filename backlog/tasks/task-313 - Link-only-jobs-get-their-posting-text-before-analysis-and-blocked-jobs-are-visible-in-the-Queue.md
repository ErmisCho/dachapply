---
id: TASK-313
title: >-
  Link-only jobs get their posting text before analysis, and blocked jobs are
  visible in the Queue
status: In Progress
assignee: []
created_date: '2026-10-19 14:37'
updated_date: '2026-10-19 16:22'
labels:
  - backend
  - frontend
dependencies: []
priority: high
ordinal: 313000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Live run 2026-10-19 (TASK-312 AC9): 5 new link-only jobs were analysed via evaluate-with-model; 4 came back maybe, but 3 had no posting text, so the prep gate ('The job has no usable posting text yet.') refused them and the Queue page showed nothing about them. The owner chose: fetch the posting text before analysing, and list anything still blocked in the Queue with the reason and a Retry.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Before the model evaluation (evaluate-with-model) and the Analyze-selected prompt are built, every selected job that has a URL but no meaningful posting text gets its posting fetched; a meaningful fetched text becomes the job's accepted text; jobs that already have meaningful text are not fetched
- [ ] #2 A failed fetch does not fail the analysis; it records source_fetch_error and the analysis still runs
- [ ] #3 The Queue API lists each unapplied job whose preparation was refused (a stored reason, no document variants) as a blocked item with that reason; in-progress analysis and 'files already exist' are not listed as blocked
- [ ] #4 The Queue page shows a Blocked section with each job, the reason and a Retry button
- [ ] #5 Retry on a blocked item first fetches the posting when the job is link-only, then re-runs preparation; the job's documents join the queue when the gate now passes, otherwise the item stays blocked with the current reason
- [ ] #6 Tests cover the fetch-before-analysis, the blocked listing and the blocked retry; full backend and frontend suites pass
- [ ] #7 Verified on localhost: Retry on the 3 blocked jobs from the live run (1875, 1847, 1845) fetches their text and queues documents, or shows why not
- [ ] #8 Owner rule 2026-10-19: when a job's text is link-only or thin (under 300 non-link characters), a longer fetched posting replaces it directly on every fetch path and status, with nothing staged for review; substantial text keeps the review step
<!-- AC:END -->
