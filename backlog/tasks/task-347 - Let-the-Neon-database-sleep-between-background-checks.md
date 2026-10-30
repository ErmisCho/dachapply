---
id: TASK-347
title: Let the Neon database sleep between background checks
status: In Progress
assignee: []
created_date: '2026-10-30 17:30'
updated_date: '2026-10-30 20:50'
labels:
  - backend
  - ops
dependencies: []
priority: high
ordinal: 347000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
2026-10-30: production and localhost went down with Neon's "Your account or project has exceeded the quota". Second Neon project in nine days (lively-wave ~10-21/10-23, fancy-paper 10-30).

Measured on the new database (delicate-bar) over 11 minutes with the local app running and no one using it: a burst of 13-15 transactions every 5 minutes (16:48:50, 16:53:53). That is mailbox_loop.TICK_SECONDS = 300, which equals Neon's 5-minute scale-to-zero window, so the compute never suspends while the local app runs (~6 CU-hours/day at 0.25 CU against a 50-100 CU-hour monthly allowance). The loop arrived 2026-10-09 (TASK-276); before that the check ran hourly from GitHub Actions and the quota was never hit.

The mail check itself is already hourly (UserProfile.mailbox_check_cadence_minutes=60); the loop only asks the database every 5 minutes whether it is due, and a skipped check still writes a MailboxRun row.

Owner decisions, 2026-10-30: mail checks hourly between 08:00 and 20:00 (the existing profile check window); the demo scheduler also only inside 08:00-20:00; the uptime probe hourly instead of every 30 minutes. Target: roughly 35 CU-hours/month in total.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Between due checks the local mailbox loop does not touch the database: it computes when the next check is due (cadence from the last run, the profile's check window) and sleeps until then, instead of polling every 5 minutes
- [x] #2 Outside the check window the loop makes no database contact at all, and writes no MailboxRun rows (no `outside_window` skip rows)
- [x] #3 Inside the window a due check still runs at the profile cadence, a pending MailboxCheckRequest is handled on the next wake, and application_prep.daily_tick still runs on each wake
- [x] #4 The demo scheduler touches the database at most once per local day, and only between 08:00 and 20:00; seeding and send_due_digests still run once a day
- [x] #5 No other in-process mechanism (the psycopg pool's background reconnects included) opens a connection to Neon while the app is idle between wakes — measured, not argued
- [x] #6 Measured against a real Neon database with the local app running idle: no queries for at least 55 consecutive minutes between two scheduled wakes (sampled from a separate connection, sample cadence stated)
- [x] #7 Uptime monitor probes hourly instead of every 30 minutes, still only weekdays 08:00-18:00 Berlin
- [x] #8 Backend tests green (`cd backend && uv run pytest -q`), with tests covering the next-wake calculation (inside window, outside window, window crossing midnight, pending request)
- [ ] #9 The owner's profile check window is 08:00-20:00 on the database the app uses (after the fancy-paper data is restored, since the restore replaces the profile row)
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Measured 2026-10-30 against the new Neon DB (delicate-bar), branch server `runserver --noreload` with DB_POOL=1 and its own application_name, pg_stat_activity sampled every 5 s from a separate connection:

- Run 1 (pool min_size 1): startup 17:43:47, then no queries for 45 min; the loop woke exactly on schedule (last run 17:28:48 + 60 min + 5 s) but hit `PoolTimeout: couldn't get a connection after 10.00 sec` and skipped the check for an hour.
- Cause, measured separately: Neon silently drops a connection idle for 50 min (fine at 7 min). The first query on it takes ~19 s to fail ("server closed the connection unexpectedly"), longer than the pool's 10 s timeout. The old 5-minute loop had hidden this by never letting the pooled connection idle.
- Fix: pool min_size 0 (the pool closes idle connections after max_idle 240 s), and a failed schedule read retries after 60 s, doubling, capped at 1 h.
- Run 2 (fixed): startup 19:19:02; pool connections closed at 19:27 and 19:31; wake 19:32:29 ran, its connection closed at 19:39:05; **no connection at all from 19:39:05 to 20:32:29**; wake 20:32:29 ran on a fresh connection, closed at 20:39:06. App queries 19:32:34 to 20:32:29 = **59 min 55 s gap** (AC6).
- Both wakes in run 2 logged "No usable Gmail OAuth refresh token": the worktree has no token file. The run was still claimed, so this does not touch the scheduling.
- Suite: 1884 passed (no .env in the worktree). Two email tests fail only when a real `.env` sits in the checkout root (pre-existing, not hermetic): test_api.py::test_one_failing_send_does_not_stop_the_rest_of_the_batch, test_email_verification.py::test_registration_survives_a_mail_host_that_is_down.
- Mutation check: disabling the "touch no database before `_next_wake`" guard fails 2 loop tests.

AC9 is open: set the owner's mailbox_check_window to 08:00-20:00 after the fancy-paper data is restored, since the restore replaces the profile row.
<!-- SECTION:NOTES:END -->
