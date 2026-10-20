---
id: TASK-317
title: >-
  Usage-limit failures show the real reason and retry automatically after the
  reset
status: In Progress
assignee: []
created_date: '2026-10-19 17:19'
updated_date: '2026-10-20 17:00'
labels:
  - backend
  - frontend
dependencies: []
priority: high
ordinal: 317000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Live 2026-10-19: Codex usage limit hit; Queue showed only 'The selected model could not complete the request.' while the provider said 'You've hit your usage limit ... try again at 6:51 PM'. Owner chose: show the reason and auto-retry after the reset.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 When a provider reports a usage/rate limit, the error summary says so in plain words including the reset time when given (e.g. 'Usage limit reached; resets at 18:51'), instead of the generic text; other failures are unchanged
- [x] #2 Queue variants and requirements analyses that failed on a usage limit are re-queued automatically shortly after the reset time (or after a fixed back-off when no time is given), at most a bounded number of times; the Queue page shows when it will retry
- [x] #3 Automatic retries survive a server restart (same serving-process guard as the queue resume) and never retry other kinds of failure
- [x] #4 Tests cover parsing the reset time, the plain-words summary, scheduling and the bounded retry, each failing when its logic is removed; targeted backend tests, vitest and tsc pass; CI green
- [x] #5 Verified on localhost: a usage-limit failure shows the reason and retry time on the Queue page
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Merged in PR #305 and live on localhost 2026-10-19 (queue items carry retry_at). AC5 waits for the next real usage limit: one cannot be triggered on demand.

2026-10-20 AC5 measured on a localhost scratch server: a fake provider emitted codex's real text "You've hit your usage limit ... try again at 6:50 PM" through the real _provider_failure/cv_tasks/_finish path; the Queue page showed 'Failed: Usage limit reached; resets at 18:50. Retries automatically at 18:51' (API retry_at 18:51:00+02:00). At 18:51:00 it re-queued and ran by itself, failed again and was rescheduled for the next day (bounded). Not a live provider limit; that cannot be triggered on demand.
<!-- SECTION:NOTES:END -->
