---
id: TASK-276
title: 'Mailbox check runs inside the local app only, while it is running'
status: Done
assignee: []
created_date: '2026-10-09 11:49'
updated_date: '2026-10-09 12:09'
labels:
  - mailbox
  - local
dependencies: []
ordinal: 273000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner, 2026-10-09: automatic functions should run only when the owner runs the app locally, on their machine. Replaces TASK-275's Windows scheduled task (never registered). The in-process scheduler pattern in services/demo_scheduler.py already starts only under runserver.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Running the local app (runserver via scripts/dachapply-local-runtime.cmd) starts a background mailbox loop that runs the check_mailbox logic (pending manual request first, then the cadence-gated tick) without any Windows scheduled task
- [x] #2 The loop never starts under gunicorn (Azure), pytest, or management commands other than runserver, and starts once only under the autoreloader
- [x] #3 Gmail OAuth works from the runtime worktree: the launcher makes dachapply-gmail-oauth-token.json available there the same way it links .env
- [x] #4 scripts/register-mailbox-task.ps1 is removed and docs/README/workflow comments describe the in-app local loop instead
- [x] #5 Measured on the owner's machine: with the local app running, a new MailboxRun row appears without anyone pressing a button
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Verified on owner's machine 2026-10-09: runtime moved to 4fd03f6, runserver started 14:08:26, MailboxRun created 14:08 with no trigger, no error (Gmail auth OK via linked token). CI green on #216; agent full suite 1386 passed.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
In-process 5-min mailbox loop and demo/digest scheduler start only under runserver; launcher links the Gmail token.
<!-- SECTION:FINAL_SUMMARY:END -->
