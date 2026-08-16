---
id: TASK-103
title: Account deletion destroys jobs that belong to someone else
status: To Do
assignee: []
created_date: '2026-08-16 16:05'
labels:
  - backend
  - data-loss
  - privacy
dependencies: []
priority: high
ordinal: 104000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`delete_account` (backend/jobradar/views.py:375) selects what to delete with

    JobLead.objects.filter(Q(created_by=user) | Q(submitted_for=user))

which is exactly the rule TASK-84 removed from `services/access.py` because it conflates "created
it" with "owns it". Every other consumer now routes through `access.owned_by`, which says a job
belongs to the person it was submitted **for**. Deletion did not follow.

Consequence: a friend who submitted job links for someone else and later deletes their own account
takes the recipient's jobs with them — along with the recipient's evaluations, notes and follow-ups,
which are deleted by the `job__in=owned_jobs` cascades on the next lines. The recipient is not
notified, is not asked, and has no way to recover the rows.

This is not new — the old rule had the same effect — but it is now the single place in the codebase
that still believes a submitter owns what they handed over, so it reads as an oversight rather than
a policy. It also became more likely to matter: TASK-92 made invite codes user-owned, so submissions
now routinely arrive from accounts that are not the recipient's.

Found during Wave 8 by the agent implementing TASK-84, which had no acceptance criterion covering
deletion. Not fixed there rather than widening that task's scope silently.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Deleting an account never deletes a job that `access.owned_by` says belongs to a different user
- [ ] #2 The deleting user's own jobs, evaluations, notes and follow-ups are still fully removed
- [ ] #3 Jobs the deleting user submitted for someone else survive with the recipient's data intact, and the recipient's board is unchanged apart from losing the submitter's name
- [ ] #4 The deletion summary the endpoint returns counts what is actually deleted, not what the old query matched
- [ ] #5 Backend tests cover a submitter deleting their account while a recipient holds evaluations and notes on the handed-off job
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
The fix is to reuse `access.owned_by(user)` here the way `user_data_portability.owned_jobs()` was
changed to during TASK-84, rather than restating the predicate a third time. That is the whole point
of having one ownership rule.

Decide explicitly what happens to `created_by` on a surviving handed-off job: the FK will need to
become null (or point at a tombstone) when the creator's `User` row goes away, and the board shows
"Added by" from it. Check the on_delete behaviour before assuming a null is safe — a CASCADE there
would delete the job anyway and make the rest of this fix pointless.
<!-- SECTION:NOTES:END -->
