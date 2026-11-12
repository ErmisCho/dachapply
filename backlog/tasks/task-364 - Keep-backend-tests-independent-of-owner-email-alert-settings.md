---
id: TASK-364
title: Keep backend tests independent of owner email-alert settings
status: Done
assignee:
  - '@pi'
created_date: '2026-11-11 14:46'
updated_date: '2026-11-12 09:25'
labels:
  - testing
  - backend
dependencies: []
modified_files:
  - backend/config/settings_test.py
  - docs/verification-2026-11-12-queue-guidance.md
priority: medium
type: bug
ordinal: 364000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
During TASK-358/359/360 verification, the standard backend suite failed because ERROR_ALERT_EMAILS from the owner .env caused deliberate logged test failures to append an owner-alert email to the locmem outbox. The same failing test and full suite passed with a process-local empty ERROR_ALERT_EMAILS. Make the default test invocation independent of that host configuration without changing production alerting. Existing isolation covers database/Gmail/Neon settings but not owner error-alert recipients. Evidence: docs/verification-2026-11-11-analysis-queue.md and .orchestrator/debug/01a1c9b7-takeover-baseline-1.md.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The previously failing test_one_failing_send_does_not_stop_the_rest_of_the_batch passes with a non-empty inherited ERROR_ALERT_EMAILS, using the normal test command and no manual environment workaround.
- [x] #2 Tests cannot send or collect unintended emails to real owner-alert recipients; tests deliberately exercising alert delivery can configure explicit fixture recipients.
- [x] #3 Production error-alert configuration and existing error-alerting tests remain unchanged in behavior.
- [x] #4 The canonical backend suite passes with inherited owner-alert settings present, and the existing CI configuration without owner secrets remains green; regression evidence shows the host-configuration failure before the fix.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Reproduce the existing digest-send test with a safe non-empty inherited alert recipient. Disable inherited ADMINS in test settings only; retain explicit alert-test overrides. Rerun digest/alert tests and the canonical full suite with inherited settings.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Inherited fixture-recipient baseline failure was reproduced. After isolating ADMINS in test settings, the digest and existing alert tests passed with inherited ERROR_ALERT_EMAILS present. Full suite initially had unrelated poll-query and Windows timing failures; those are now passing in the 56-test focused correction run. Canonical rerun pending.
2026-11-12: re-verified on main: 36 alert tests pass with ERROR_ALERT_EMAILS=owner@example.invalid inherited; CI green on PR 393.
<!-- SECTION:NOTES:END -->
