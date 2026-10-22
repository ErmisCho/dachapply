---
id: TASK-338
title: Reminder emails skip the demo account and undeliverable addresses
status: Done
assignee: []
created_date: '2026-10-22 07:34'
updated_date: '2026-10-22 13:25'
labels:
  - backend
dependencies: []
priority: high
ordinal: 338000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner 2026-10-22: a 'DACHApply reminders: 2 items need attention' digest went to demo@dachapply.com and bounced to the owner ('DNS Error: DNS type mx lookup of dachapply.com responded with code NXDOMAIN'). followup_digest.send_due_digests mails every active user with due items; the demo account has demo follow-ups. Measured read-only: 9 accounts: 4 gmail.com, 1 dachapply.com (demo), 4 example.com (reserved domain, would bounce the same way).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The demo account never gets a digest
- [x] #2 Addresses on reserved/undeliverable domains (example.com/.net/.org, *.example, *.test, *.invalid, *.localhost) never get a digest
- [x] #3 Real accounts still get theirs; a test covers demo, reserved and real recipients
- [x] #4 Deployed so the live site's daily run uses it too
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Merged #339, deployed with #340. send_digest skips the demo account and RFC 2606 example domains; 27 digest tests pass. Next morning digest is the live check.
<!-- SECTION:NOTES:END -->
