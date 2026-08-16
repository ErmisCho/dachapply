---
id: TASK-84
title: Restrict friend access to submitted jobs after handoff
status: Done
assignee:
  - '@claude'
created_date: '2026-08-16 00:43'
updated_date: '2026-08-16 16:10'
labels:
  - multi-user
  - privacy
  - backend
dependencies: []
priority: medium
ordinal: 89000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`accessible_jobs` grants access via `Q(created_by=user) | Q(submitted_for=user)` (backend/jobradar/services/access.py:10-22), so a friend who submitted a job for someone else retains full read and mutate access to it forever — including the recipient's later evaluations, notes, and follow-ups (nested reads at views.py:362-376; note/follow-up viewsets at views.py:380, 389, 400).

Between two actual friends today this is tolerable; the moment less-trusted users join, the submitter of a link can watch the recipient's private interview prep and recruiter notes accumulate on "their" job.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A user who submitted a job for someone else sees at most submission status (the job exists, a coarse status), not the recipient's evaluations, notes, or follow-ups, and cannot mutate the job
- [x] #2 The recipient's own access and workflow are unchanged
- [x] #3 Jobs a user created for themselves are unaffected
- [x] #4 Backend tests cover the submitter-visibility boundary in both directions
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
The root cause is that access.py conflates "created it" with "owns it". Split the created-for-someone-else case into a limited queryset/serializer rather than adding per-endpoint guards — access.py is the shared function every consumer routes through, so one fix there covers all nine call sites.

### Closing notes (2026-08-16)

Fixed at the root, as the task demanded: one predicate in `access.py` —

> A job belongs to the person it was submitted **for**; when it was submitted for nobody, to whoever
> created it. Submitting a job for someone else buys a read-only receipt, never ownership.

`Q(submitted_for=user) | Q(created_by=user, submitted_for__isnull=True)`. Because every consumer
routes through `accessible_jobs`, that one change removes the submitter's access to the recipient's
workflow across all nine call sites at once, rather than nine per-endpoint guards that a tenth
endpoint would forget.

**Measured end to end against the running server, in both directions.** A submitter handed a job to
a recipient, who then added an interview note, an evaluation and a recruiter note:

    submitter's list row:  submission_only: True
                           status: "new"   (the real status is "interview")
                           status_date: "", latest_evaluation: None, interview_note: ""
                           leak check: neither the evaluation text nor the interview note
                                       appears anywhere in the row
    submitter direct:      GET /jobs/<id>/            -> 404
                           GET /jobs/<id>/notes/      -> 404
                           GET /jobs/<id>/followups/  -> 404
                           PATCH /jobs/<id>/          -> 404
    submitter's own job:   no submission_only key, full fields          (AC3)
    recipient:             status "interview", the private interview note,
                           fit_score 91, the private evaluation summary  (AC2)

The implementing agent also ran the counterfactual — reverting `owned_by` to the old rule makes the
test fail with `assert 200 == 404` on the detail route — so the guard is load-bearing rather than
decorative.

**A leak outside the nine call sites was found and closed:** `user_data_portability.owned_jobs()`
restated `created_by OR submitted_for` in its own words, so a submitter's data export contained the
recipient's evaluations and notes. It now borrows `owned_by` too.

**Interaction with TASK-92, deliberately handled:** for a job with `created_by` null (an anonymous
invite-code submission) the rule matches on `submitted_for` alone, so it is *fully* the recipient's —
list, detail, mutation, notes, export, stats — exactly as if they had added it themselves. A row with
both fields null stays staff-only, unchanged.

**Accepted regression, stated rather than hidden:** re-posting a handed-off URL through the
authenticated `POST /api/jobs/` route no longer raises a duplicate conflict for the submitter,
because the recipient's copy is no longer in their `accessible_jobs`. Widening it back would leak
the recipient's job in the conflict payload — which is precisely what AC1 forbids — and friend
submitters are routed to `/public-submit`, where dedupe still works against the recipient's board.

**Filed, not fixed — TASK-103:** `delete_account` still selects with the old
`created_by OR submitted_for` rule, so a submitter deleting their account destroys the recipient's
jobs, evaluations and notes. Out of this task's ACs, and now the only place in the codebase that
still believes a submitter owns what they handed over.
<!-- SECTION:NOTES:END -->
