---
id: TASK-93
title: Verify email at registration and stop email enumeration
status: Done
assignee:
  - '@claude'
created_date: '2026-08-16 00:43'
updated_date: '2026-08-16 16:25'
labels:
  - security
  - multi-user
  - backend
dependencies: []
priority: low
ordinal: 98000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Registration activates and logs the account in instantly with any unverified email (backend/jobradar/views.py:100-116, login at 115). The friend-request lookup in the same flow answers "Friend username or email not found" (views.py:110-111) — a free oracle for whether any email address has an account here.

Neither matters much among friends; both matter the moment strangers can register (registration is open — invite codes gate only anonymous /public-submit, views.py:444-447).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 New registrations must verify their email before (at minimum) friend requests and any future invite/code features work; core solo usage may remain immediate
- [x] #2 The friend-request path returns an indistinguishable response for known vs unknown emails (the request is recorded or silently dropped, never "not found")
- [x] #3 Existing accounts are grandfathered as verified
- [x] #4 Backend tests cover the unverified-gating and the indistinguishable response
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
The password-reset token flow (views.py:172-245, working since TASK-2) is the template: same token pattern, same send_mail infrastructure. A verified flag on UserProfile beats a separate model.

### Closing notes (2026-08-16)

**AC2 was solved by deleting the branch, not rewording it.** Registration now stores the named friend
*as typed* and resolves it only when the address is confirmed. With no lookup at registration there
is no hit/miss to leak — not in the body, and not in the work done. Measured independently against
the running server, three registrations differing only in the friend named:

    friend = an address that exists      -> HTTP 201, body {"email_verified": false,
    friend = an address that does not    -> HTTP 201,       "is_friend_submitter": false,
    friend = not named at all            -> HTTP 201,       "requested_submit_for_username": null,
                                                            "submit_for_username": null}

Byte-identical in all three cases. `requested_submit_for_username` is now always `null` at
registration — echoing the resolved username was a second oracle as loud as the old 400.

The implementing agent also asserted equal **query counts**, and found a confound worth recording:
the first draft failed at 37 vs 34 queries, which turned out to be the usage middleware charging the
first request of any test for its `SiteDailyUsage`/`SiteVisitor` rows, not the friend lookup.
Reversing the probe order proved it. The test now warms up first, so it measures registration rather
than fixture order.

**AC1** gates friend-approve and invite minting on the verified flag; solo board usage stays
immediate, as the AC allows. Minting was gated deliberately: an invite code is a funnel — anonymous
submissions land on the minter's board — so an unverified stranger on a throwaway address could
start collecting other people's job links. Wave 8's TASK-92 turned the AC's "any future invite/code
features" clause into the present tense. Listing and revoking stay open, since neither grants
anything.

**AC3's grandfathering verified across all three shapes**, including the trap where a legacy account
has no `UserProfile` row at all:

    legacy account with a profile row     email_verified=True   mint -> 201
    brand-new account                     email_verified=False  mint -> 403
    legacy account with NO profile row    email_verified=True   mint -> 201

**The verification flow driven end to end**, including tamper and replay:

    before                      email_verified: False
    POST with a mangled token   400
    POST with the real token    200  {"detail":"Email address confirmed."}
    after                       email_verified: True, mint -> 201
    same link again             200  (idempotent)

The token drops `last_login` and `password` from its hash, because registration logs the account
straight in and every later login would otherwise invalidate the link before the user opened their
inbox.

**Known remaining oracle, deliberately out of scope:** registration still answers
`Email already exists` for the *registering* address. That is inherent to open registration and is
not the friend-request path AC2 names; closing it needs an email-first "we sent you a link either
way" flow, which is its own task.

**A UX cost worth naming:** a user who mistypes their friend's address now gets silence instead of an
error. That is what "indistinguishable" buys. `/public-submit` still tells them to confirm their
address first, and the friend never appears in `/auth/me/`.

Deploy: nothing manual. `scripts/start-container.sh` already runs `migrate --noinput`, and 0028 is
two AddFields with no backfill and no table rewrite. `FRONTEND_URL` and the Brevo credentials are
already in use by password reset.

<!-- SECTION:NOTES:END -->
