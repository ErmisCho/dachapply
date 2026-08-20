---
id: TASK-151
title: The deployed site hides the run control behind the CV-owner gate
status: Done
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
- [x] #1 The run section's visibility is gated on an owner property that is true for the owner's account on EVERY deployment of the same database — stated explicitly which property and why it cannot diverge between deployments
- [x] #2 On the deployed (credential-less) site, the owner sees the run control, pressing it queues a `MailboxCheckRequest`, and the UI states the run has NOT started yet — verified live, which also closes TASK-124 AC2
- [x] #3 A non-owner account (a friend-submitter) still does not see the run section — asserted by whatever test or measurement fits the chosen gate
- [x] #4 `can_generate_cv` keeps meaning exactly what its model help_text says; CV generation gating is untouched
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-08-20 close-out. Verified on the DEPLOYED site 2026-08-20 after PR #56 (merge edeb82f, deploy green, live HTTP 200): the run control renders for the owner (is_staff true, can_generate_cv false - the two are now correctly independent), GET /api/mailbox-runs/status/ returns 200 where it returned 404 before, and pressing Run POSTs /api/mailbox-runs/run-now/ -> 200 {"queued":true,"request_id":1} with the UI stating: "This backend has no mail credentials. The request has been recorded for the owner's machine to pick up on its next check - it has NOT started yet." The MailboxCheckRequest row is confirmed in the production database (1 row, requested_by the owner). The fix had two halves and BOTH shipped: the frontend gate (PR #55) and the backend one (PR #56) - is_mailbox_owner(user) = authenticated and is_staff, applied to the mailbox endpoints only, with the CV endpoints deliberately left on is_cv_owner because the CODEX_CV_ENABLED kill switch is correct for them (AC4). Tests that encoded the old gate were updated rather than deleted, and a test pins that CV generation still refuses when the kill switch is off. Known bounded divergence worth stating: services._owner_user() still resolves "the owner" by CODEX_CV_OWNER_EMAIL while the views now gate on is_staff; in production both resolve to the same single account (1 of 9 is staff), so this is latent rather than active.

2026-08-20, measured. The description above named the mechanism imprecisely; the real one, proven
live, is worth stating exactly because it has TWO halves:

`can_generate_cv` in the API payload is `is_cv_owner(user)`, whose FIRST line is
`if not (settings.CODEX_CV_ENABLED and user.is_authenticated): return False`, and
`CODEX_CV_ENABLED = env_bool('CODEX_CV_ENABLED', DEBUG)` — so it is True on the owner's machine
(DEBUG=True) and False in the deployed container. Proof by elimination: the deployed
`/api/auth/me/` returns `can_generate_cv:false` (HTTP 200) for the owner's account while the same
shared database holds `UserProfile.can_generate_cv = True` and `is_cv_owner()` returns True locally
— and the deployment reads the SAME database (the live site returns the very rows ingested from
this machine: job 37 with 10 messages, 5 owner-sent). So the flag gates "is the CV subsystem
switched on for this server", never "is this the owner".

FRONTEND half (shipped, PR #55): the run section is now gated on `is_staff` — a plain column,
already in `/auth/me/`, cached by RequireAuth on every route change, 1 of 9 accounts. Verified on
the deployed site: the control renders with `is_staff:true, can_generate_cv:false`.

BACKEND half (found by pressing the button after the deploy, still open at time of writing): the
control's POST to `/api/mailbox-runs/run-now/` returns **404 `{"detail":"Not found."}`**, because
`run_now` (views.py) carries the same `is_cv_owner` gate, as do `MailboxRunViewSet.get_queryset`
(returns `.none()`), `status_view`, the mailbox-messages queryset, and the owner-gated POST near
line 1107. Every mailbox endpoint is therefore dead on the deployed site. The fix is a dedicated
`is_mailbox_owner` predicate for the MAILBOX endpoints only; CV endpoints keep `is_cv_owner`,
because the kill switch is correct for them (AC4).
<!-- SECTION:NOTES:END -->
