---
id: TASK-319
title: >-
  A job whose real posting arrives after a link-only analysis is re-analysed
  before documents are queued
status: In Progress
assignee: []
created_date: '2026-10-19 18:44'
labels:
  - backend
dependencies: []
priority: high
ordinal: 319000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Live 2026-10-19: ÖBB job 1845 was analysed from its link alone ('maybe'); when TASK-318 fetched the real ad, Retry queued a CV on that old guess; re-analysing the real ad gave 'skip' (44) and the CV had to be cancelled by hand. Owner chose: re-analyse first by default, with a switch to change it later.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 When a job's link-only or thin text is replaced by a fetched posting (queue Retry, job-page fetch, automatic refresh) and the job already has an evaluation, the job is re-analysed with the real text in the background before any documents are queued; apply/maybe then queues documents (existing TASK-312 hook), skip queues nothing
- [ ] #2 The pre-analysis fetch (evaluate-with-model / Analyze prompt) does not trigger an extra re-analysis
- [ ] #3 Setting DACHAPPLY_REANALYSE_LATE_TEXT (default on) switches it off, restoring today's behaviour; documented in .env.example
- [ ] #4 A failed re-analysis (e.g. usage limit) leaves the job visible in the Queue as blocked with the reason and Retry; no documents are queued on the old guess
- [ ] #5 Tests cover re-analyse-then-queue, skip queues nothing, setting off, no double analysis, failure shows blocked; each fails when its logic is removed; CI green
- [ ] #6 Verified on localhost on a link-only job
<!-- AC:END -->
