---
id: TASK-184
title: Scope the board to the signed-in user, not every row
status: To Do
assignee: []
labels:
  - backend
  - multi-user
  - privacy
  - bug
dependencies: []
priority: high
ordinal: 184000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner, 2026-08-24: *"remove from account ermis.chorinopoulos@gmail.com any demo listings and don't
allow them back to enter as job listings."*

Investigated before acting, and **nothing should be deleted** — the listings are not on the owner's
account. Measured against production:

    ermis.chorinopoulos@gmail.com   staff=True  super=True   owned=83   accessible=93
    demo@dachapply.com              staff=False super=False  owned= 9   accessible= 9

    jobs on the owner's board that are NOT theirs: 10
      demo@dachapply.com 6, sophie.recruiter 1, max.referrer 1, anna.referrer 1, unowned 1

The board renders `accessible_jobs`, which grants staff **every row in the table**. The owner is a
superuser, so Swiss AI Systems, MedTech Rails GmbH, FinTech GmbH, AI Search Lab, CloudOps AG, Green
Energy Analytics, Helvetic Frontend Studio and Legacy Enterprise SE appear on their board while
belonging to the demo account and three referral fixtures. Deleting them would empty the public demo
and break the friend-referral fixtures, and would not stop the next signup's jobs appearing either.
The listings are not leaking INTO the account; the VIEW is unscoped.

**Owner decision, 2026-08-24**, chosen over a staff-only "show all" toggle and over deleting the demo
accounts: the board always shows only the signed-in user's own jobs. Admin oversight stays in Django
admin, which is the right place for it.

**One name collides and must survive.** `Dynatrace` is both a demo company and a company the owner
genuinely applied to. Their two Dynatrace jobs are real — real careers URLs, `source=dynatrace.com`,
and **26 mailbox messages attached to job 656**. Any company-name-based cleanup would have destroyed
them, which is why this task changes a queryset and deletes nothing.

**This is a privacy defect, not a cosmetic one.** The mechanism is `is_staff`, not anything
demo-specific: the day a second real person signs up, their jobs appear on the owner's board too.
Today the leak is one-directional (demo sees only its own 9), which is luck of who is staff, not
design.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The board, its stats and its panels show only jobs the signed-in user owns — measured against production before and after as counts per account, not asserted from the queryset
- [ ] #2 A second user's jobs are not visible to the owner and vice versa, proven by a test with two users where the assertion fails if the queryset is widened back
- [ ] #3 No job rows and no accounts are deleted; the public demo login still works and still shows its own 9 jobs, verified end to end
- [ ] #4 The owner's real Dynatrace jobs (536, 656) are untouched, and job 656 still has its 26 attached messages
- [ ] #5 Every board-facing endpoint is covered, not just the job list — state which endpoints were audited and what each now scopes on, including `/api/stats/`, the dashboard panels and the mailbox endpoints
- [ ] #6 Staff oversight is still possible somewhere, and where it now lives is stated
- [ ] #7 The mailbox endpoints' own gate (`is_mailbox_owner`, currently `is_staff`) is reviewed against this change and the decision stated — a mailbox scoped by staff-ness while the board is scoped by ownership is a contradiction that must be resolved deliberately, not left
- [ ] #8 Backend suite green; the board verified in a browser showing the owner's own count and not the all-rows count
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
`services/access.py` holds `accessible_jobs`; `services/followup_digest.py` holds `owned_jobs`
(`created_by=user OR submitted_for=user`), which already has the right semantics and a docstring
explaining exactly why it is not `accessible_jobs`: *"that grants staff every row in the table, which
is right for the admin API and very wrong for a personal reminder email."* The same argument applies
to the board; this task is largely making the board agree with a rule the codebase already wrote down.

Do not simply swap every call site blind. AC5 exists because the board is not one endpoint — the job
list, `/api/stats/`, the dashboard panels and the mailbox endpoints each fetch their own rows, and a
partial change would leave the counts disagreeing with each other, which reads as data loss.

`MailboxMessage` has no owner column at all; ownership is reached via `matched_job`. AC7 is there
because scoping the board by ownership while the mailbox stays gated on `is_staff` leaves a real
inconsistency — decide it, state it, do not discover it later.

The 1 unowned job (`created_by` NULL) needs a decision too: it currently appears for staff and would
vanish for everyone. Say what happens to it rather than letting it disappear silently.
<!-- SECTION:NOTES:END -->
