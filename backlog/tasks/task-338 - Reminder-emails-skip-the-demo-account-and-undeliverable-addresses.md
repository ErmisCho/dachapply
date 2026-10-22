---
id: TASK-338
title: Reminder emails skip the demo account and undeliverable addresses
status: To Do
assignee: []
created_date: '2026-10-22 07:34'
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
- [ ] #1 The demo account never gets a digest
- [ ] #2 Addresses on reserved/undeliverable domains (example.com/.net/.org, *.example, *.test, *.invalid, *.localhost) never get a digest
- [ ] #3 Real accounts still get theirs; a test covers demo, reserved and real recipients
- [ ] #4 Deployed so the live site's daily run uses it too
<!-- AC:END -->
