---
id: TASK-151
title: The deployed site hides the run control behind the CV-owner gate
status: To Do
assignee: []
labels:
  - frontend
  - mailbox
  - bug
dependencies:
  - TASK-124
priority: medium
ordinal: 151000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found 2026-08-20 while verifying TASK-124 AC2 on the deployed site. The Mailbox page's whole "Run
check now" section renders only when `storedUser()?.can_generate_cv` is true (App.tsx, the `owner`
const). `can_generate_cv` comes from `is_cv_owner()` — the per-account flag OR the env-based CV
owner check — and on the deployed container it is false for the owner's own account (verified live:
`/api/auth/me/` returns `can_generate_cv: false` there, true on the owner's machine against the
same database).

Consequence: the credential-less deployment — exactly the place where pressing run is supposed to
QUEUE a request for the owner's machine (TASK-124 AC2's whole scenario) — never shows the control
at all. The queue path is fully implemented and test-proven server-side
(`MailboxCheckRequest` + the "has NOT started yet" wording); it is unreachable in the deployed UI.

The gate was presumably meant as "is the site owner", and `can_generate_cv` happened to be the
only owner-ish flag available; its env half makes it deployment-dependent, which is wrong for this
use.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The run section's visibility is gated on an owner property that is true for the owner's account on EVERY deployment of the same database — stated explicitly which property and why it cannot diverge between deployments
- [ ] #2 On the deployed (credential-less) site, the owner sees the run control, pressing it queues a `MailboxCheckRequest`, and the UI states the run has NOT started yet — verified live, which also closes TASK-124 AC2
- [ ] #3 A non-owner account (a friend-submitter) still does not see the run section — asserted by whatever test or measurement fits the chosen gate
- [ ] #4 `can_generate_cv` keeps meaning exactly what its model help_text says; CV generation gating is untouched
<!-- AC:END -->
