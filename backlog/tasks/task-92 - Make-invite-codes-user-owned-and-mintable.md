---
id: TASK-92
title: Make invite codes user-owned and mintable
status: Done
assignee:
  - '@claude'
created_date: '2026-08-16 00:43'
updated_date: '2026-08-16 16:10'
labels:
  - multi-user
  - backend
dependencies: []
priority: low
ordinal: 97000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Anonymous invite-code submissions create ownerless job rows: PublicSubmissionSerializer.create sets no owner (backend/jobradar/serializers.py:243-247) and ownership is assigned only for authenticated submitters (views.py:473-474), so anonymous submissions are visible only to staff (services/access.py:20-21). This works today solely because the owner happens to be staff — for any other user, "share a code with friends" is broken by design.

InviteCode also has no owner FK (models.py:168-175), codes are whatever an admin typed into a CharField (admin.py:583-587 — no generation helper, no usage audit), and only Django admin can create them.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 InviteCode gains an owner; anonymous submissions through a code land as submitted_for that owner and appear on their dashboard
- [x] #2 An authenticated user can mint and revoke their own codes from the UI, with generated (not typed) code values
- [x] #3 Existing codes migrate to the current owner's account
- [x] #4 Backend tests cover code-scoped submission visibility and revocation
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
The existing 20/hour/IP throttle on public_submit (views.py:444-447) stays. `secrets.token_urlsafe` for generation — no custom code-strength logic needed.

### Closing notes (2026-08-16)

`InviteCode` gains a nullable `owner` FK and a `recipient_for()` resolver; anonymous submissions
through a code are stamped `submitted_for=owner`. Minting and revocation are a small owner-scoped
viewset in its own module (`views_invites.py`), so it did not collide with the second backend agent
working in `views.py` during the same wave.

**Measured end to end in a browser, including the anonymous half from a genuinely session-less
context:**

    mint          -> code "EVEzbAr1rxBI" (12 chars, generated), label "Anna", active
                     posting code:"CHOSEN-BY-ME" is ignored - `code` is read-only
    anonymous     -> POST /api/public/submit/ with the code, no session
                     201, submitted_for_username "verify", created_by_username ""
                     the job appears on the owner's board          (AC1)
    revoke        -> same code now returns 400 "Invalid invite code"
                     the job submitted earlier is still on the board  (AC4)

**Revocation is a soft flip of `active`, never a delete** — the row survives as the audit record of
who submitted through what, and `JobLead` has no FK to `InviteCode`, so already-submitted jobs keep
their owner. Re-activation is deliberately not offered; mint a new code.

**AC3's migration rule, and the case that would have broken CI:** "the current owner" is the
earliest superuser, else the earliest staff user, else nobody — ordered by pk so it is deterministic
with several admins, and never falling through to a plain user, since a random account inheriting
the deployment's codes would be worse than leaving them ownerless. Ownerless is a safe resting
state: `owner` is nullable and `recipient_for` returns `None`, which is byte-for-byte the
pre-TASK-92 behaviour. Verified by a real `migrate` against a genuinely empty database, which is
what a fresh checkout and CI both run.

The existing 20/hour/IP throttle on `public_submit` is untouched, and `secrets.token_urlsafe`
generates the codes — no custom code-strength logic, as the task asked.

**Two notes for later.** Minting is unthrottled: an authenticated user can create unbounded codes.
Only their own board receives the submissions, so the blast radius is their own storage, but the
`throttles.py` scaffolding is there if it ever matters. And `/public-submit` is still behind
`RequireAuth` (TASK-101), so the anonymous path proven above is currently reachable only via the
API — the UI cannot exercise it until that decision is made.

**Cross-agent note worth keeping:** this task's tests assert that the *recipient* keeps access,
deliberately, because TASK-84 was rewriting the ownership rule in the same wave. That tripwire fired:
an in-flight version of `accessible_jobs` raised
`TypeError: Cannot combine a unique query with a non-unique query` and broke `/api/jobs/` for six
tests including three here, which is how it was caught rather than by a user.
<!-- SECTION:NOTES:END -->
