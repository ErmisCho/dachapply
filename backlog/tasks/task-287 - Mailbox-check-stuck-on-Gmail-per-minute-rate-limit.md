---
id: TASK-287
title: Mailbox check stuck on Gmail per-minute rate limit
status: Done
assignee: []
created_date: '2026-10-14 08:05'
updated_date: '2026-10-14 12:48'
labels: []
dependencies: []
ordinal: 288000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Since about 2026-08-28 no new mail has been captured. Every local hourly check (mailbox_loop) fails: fetch_new() GETs every listed message back to back, Gmail answers 403 rateLimitExceeded ('Units per minute per user'), _gmail_api_request raises and the whole run is lost, so the next run starts over and fails again. Also seen: psycopg_pool.PoolTimeout in the loop tick.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A rate-limited Gmail call (403 rateLimitExceeded/userRateLimitExceeded or 429) is retried with backoff (honouring Retry-After) instead of failing the run; other 403s still fail
- [x] #2 Messages already fetched are not lost when a run fails part-way: the next run makes progress instead of restarting from zero
- [x] #3 Tests cover the retry, the give-up after a bounded wait, and the progress-kept case; each fails when its logic is removed
- [x] #4 After relaunch the local check completes on the owner's mailbox and mail newer than 2026-08-28 appears on the matching jobs
- [x] #5 Backend suite passes
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-14: #248. First run after relaunch: 323 fetched, no error; BEKO now shows its 6 emails.
<!-- SECTION:NOTES:END -->
