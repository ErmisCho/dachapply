---
id: TASK-194
title: Let the local website install the mailbox scheduled task
status: Done
assignee:
  - '@pi'
created_date: '2026-08-25 14:24'
updated_date: '2026-08-26 11:00'
labels:
  - frontend
  - backend
  - mailbox
  - windows
dependencies: []
references:
  - backend/jobradar/management/commands/check_mailbox.py
  - frontend/src/App.tsx
modified_files:
  - backend/jobradar/views.py
  - backend/install_mailbox_task.ps1
  - backend/jobradar/tests/test_mailbox_scheduler.py
  - frontend/src/App.tsx
priority: medium
ordinal: 194000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The Profile settings page currently configures mailbox cadence but does not start the local mailbox checker, which led the owner to reasonably believe 'Every hour' was already scheduling it. When the app is served from the owner's Windows machine, provide an owner-only button that idempotently creates the Windows Scheduled Task which invokes check_mailbox. Keep this unavailable on the deployed site and other platforms.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 On a loopback Windows backend, the owner sees a control explaining whether the mailbox scheduled task is installed and can install or refresh it with one click
- [x] #2 Installation idempotently creates or updates a Windows Scheduled Task that invokes this repository's check_mailbox command regularly; paths containing spaces work and mailbox cadence/window/calendar settings remain authoritative
- [x] #3 Non-owner, non-loopback, deployed, and non-Windows requests cannot execute scheduler commands and receive a safe unsupported/forbidden response
- [x] #4 The UI reports success or a useful setup error without implying that changing cadence alone starts the checker
- [x] #5 Backend tests mock OS command execution and cover success, idempotent refresh, and safety guards; frontend build remains green
- [x] #6 The Windows task interval matches the profile's saved mailbox cadence and invokes the checker with cadence bypassed, so there is one scheduling timer; saving a changed cadence locally refreshes an installed task
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Make the installer accept the saved mailbox cadence, configure that exact Windows repetition interval, and invoke check_mailbox --force so Task Scheduler is the sole cadence timer. 2. Read the installed interval from Task Scheduler XML and expose it to the local settings UI. 3. When Profile settings saves a cadence that differs from an installed task, refresh it through the existing UAC flow; keep an explicit refresh button for recovery. 4. Update mocked tests and rerun focused/full backend checks, frontend build, and PowerShell syntax validation.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Windows denies Scheduled Task creation from the normal non-elevated local server, confirmed on the owner's machine. The button therefore launches a narrowly scoped PowerShell installer through the native UAC prompt; the registered task itself runs with Limited privileges. Validation: focused scheduler tests 5 passed, complete backend suite 999 passed, frontend npm build passed, PowerShell parser reported syntax OK, and git diff --check passed.

Cadence refinement after owner review: removed the second five-minute polling interval. The installer now receives the saved profile cadence, registers that exact Windows repetition interval, and runs check_mailbox --force so only Task Scheduler owns cadence. GET status parses the task's locale-independent XML interval; local Profile Save refreshes an installed mismatched task through UAC. Validation after refinement: 6 focused tests passed, complete backend suite 1000 passed, frontend build passed, PowerShell syntax and git diff checks passed.

Superseded before merge by TASK-195: scheduled ingestion now runs hourly in GitHub Actions, so the local Windows installer/UI were removed to avoid concurrent Gmail fetchers. No DACHApply Mailbox Check task is installed on the owner's PC.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Added the local owner-only Windows task setup control and synchronized it directly with the website's saved mailbox cadence. A 60-minute website setting now creates a 60-minute Windows trigger running check_mailbox --force—no separate five-minute poll. Local cadence changes refresh an installed task through UAC; safety guards block cloud, remote, non-Windows, and non-owner calls. Verified by 1000 backend tests, frontend build, and PowerShell syntax validation.

Superseded before merge by TASK-195's cloud scheduler; the Windows scheduler implementation is intentionally not present in the final code.
<!-- SECTION:FINAL_SUMMARY:END -->
