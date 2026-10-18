---
id: TASK-289
title: Mailbox check failures are never silent
status: Done
assignee: []
created_date: '2026-10-14 08:19'
updated_date: '2026-10-18 12:40'
labels: []
dependencies: []
ordinal: 290000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner (2026-10-14): mail capture failed silently for 6 weeks (OAuth invalid_grant 08-31..09-28, then Gmail rateLimitExceeded). Errors only reached MailboxRun.error and the server log. Make failures visible: a board banner and an email alert. Depends on TASK-287/288 (same files).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 When the latest non-skipped mailbox run failed, or no run has fetched successfully for 24 h while checks are enabled, the board shows a banner with the reason in plain words and what to do (e.g. 'Gmail login expired: re-authorize')
- [x] #2 The banner disappears on the next successful run
- [x] #3 The owner gets one email alert when checks start failing (not one per hourly failure) and one when they recover, reusing the existing alert/mail path
- [x] #4 Tests cover banner condition, alert de-duplication and recovery; each fails when its logic is removed
- [x] #5 Verified on localhost: a simulated failure shows the banner; vitest, tsc and backend suite pass
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-14: #250. Health null on localhost (healthy, no banner). Banner on failure verified by test only. Mail alert is a no-op locally until ERROR_ALERT_EMAILS + SMTP are set in the runtime .env (owner).

2026-10-15: banner rendered on the localhost board with a simulated failing status.

2026-10-18: Gmail SMTP set in the local .env (owner app password). sendtestemail --admins delivered through mail_admins, the same call _alert_on_failure_transition uses.
<!-- SECTION:NOTES:END -->
