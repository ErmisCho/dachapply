---
id: TASK-101
title: Public-submit is not reachable without an account
status: Done
updated_date: '2026-08-16 19:40'
assignee:
  - '@claude'
created_date: '2026-08-16 13:10'
labels:
  - frontend
  - product
  - bug
dependencies: []
priority: high
ordinal: 102000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`/public-submit` is wrapped in `RequireAuth` like every other protected route, so an anonymous
visitor is redirected to `/login` and never sees the form.

Measured 2026-08-16 in a clean browser context with no session cookie:

    anonymous GET /public-submit -> redirected to /login
    page text: "DACHApply / Login / Start / Private job intelligence for DACH applications…"

The backend disagrees with the frontend here. `public_submit` is `AllowAny`, carries its own
20/hour/IP throttle, and accepts invite codes — the whole anonymous-submission path exists and is
tested server-side. Only the SPA route gates it.

This matters because several filed tasks rest on the opposite assumption:

- **TASK-98** ("German language pass on the public-submit flow") justifies itself as
  *"exactly the page German-speaking friends without an account actually use"*. As shipped, a
  friend without an account cannot reach it, so translating it changes nothing for that audience
  until this is fixed.
- **TASK-92** ("Make invite codes user-owned and mintable") is built around anonymous submissions
  arriving through a shared code. The API supports that; the UI offers no anonymous way in.
- **TASK-72**'s description called `/public-submit` "the flow friends use".

Either the route should be public (matching the backend), or the "share a link with a friend" story
should be retired and the tasks above rewritten. That is a product decision, not a silent fix — which
is why this is filed rather than patched.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A decision is recorded: either /public-submit is anonymous-capable, or the anonymous-submission story is retired
- [x] #2 N/A - the route was made anonymous-capable (AC1), so there is no reinterpretation for TASK-92/TASK-98 to guard against; both remain accurate as filed
- [x] #3 If it becomes public, an anonymous visitor can load /public-submit and submit with a valid invite code, verified in a browser with no session — verified by the coordinator, see notes
- [x] #4 If it becomes public, the page does not leak authenticated-only affordances (nav destinations, profile menu) to anonymous visitors — verified by the coordinator, see notes
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Making it public is a one-line route change (drop the `RequireAuth` wrapper for that path), but AC4
is the real work: `JobForm publicMode` currently renders inside the authenticated shell, and `Nav`
assumes a logged-in user. Check what an anonymous render actually shows before calling it done.

The backend needs no change either way — `public_submit` already accepts anonymous requests with an
invite code and throttles them by IP.

DECISION (2026-08-16): /public-submit is anonymous-capable. The backend already implements
anonymous submission end to end (AllowAny, its own 20/hour/IP throttle, invite-code validation);
TASK-92 (user-owned, mintable invite codes) and TASK-98 (German copy for this exact page) both
shipped on the assumption that a friend without an account reaches this page, and retiring the
"share a link with a friend" story now would mean undoing shipped work rather than avoiding it.

Frontend changes, both confined to `frontend/src/App.tsx` and `frontend/src/appUtils.ts`:
1. Route: `<Route path="/public-submit" element={<RequireAuth>...` -> `element={<JobForm publicMode/>}`.
   No other route's `RequireAuth` wrapper was touched - verified by reading the full route table
   after the edit.
2. Real gap found beyond the route: `JobForm`'s `publicMode` form had no invite-code input at all.
   `views.public_submit` requires `invite_code` in the body for any unauthenticated request
   (`if not request.user.is_authenticated: code=... InviteCode.objects.filter(code=code)...`), and
   `PublicSubmissionSerializer.create()` is what actually routes the job to the inviting owner's
   board (`InviteCode.recipient_for(invite_code)`, serializers.py:281-288) - so without this field an
   anonymous visitor could reach the page but every submission would 400 with "Invalid invite code".
   Added a German-labelled invite-code `<input required>`, shown only when `publicMode && !storedUser()`
   (an authenticated visitor - approved friend or not - skips the invite-code check server-side, so
   the field would be noise for them). Traced the full path through `views.py` and `serializers.py`
   read-only to confirm the invite code actually reaches `InviteCode.recipient_for` and lands the job
   on the right dashboard; did not modify anything under `backend/`.
3. AC4 leak check: `Nav` already gates every authenticated-only link and the profile menu behind
   `{user && ...}` where `user` comes from `storedUser()`, so a visitor with no cached
   `dachapply_user` (the real "friend with no account" case) renders only the brand link, the
   Login/Start links, and the dark-mode toggle - no nav destinations, no profile menu.
   `GuidedOnboardingTour` early-returns for `!tourUser` before it ever renders or calls `/stats/`.
   `JobForm`'s own `publicMode` branch has no authenticated-only links; the one `<Link to="/">Open
   dashboard</Link>` in the success state is already gated `!publicMode`. Did not find a code path
   that leaks an authenticated affordance to a visitor with an empty `dachapply_user` cache.
   CAVEAT (not fixed, out of this task's scope): the whole app trusts a cached `dachapply_user` in
   localStorage instantly and only reconciles it via `authMe()` inside `RequireAuth`, which no longer
   runs on this route. A device with a *stale* cached user (valid localStorage entry, expired/invalid
   session - e.g. someone else's earlier login on a shared browser) would still see the authenticated
   Nav on this one route, because nothing on `/public-submit` calls `authMe()` to refresh/clear it.
   This is a pre-existing app-wide caching trade-off, not a regression from this change, and fixing it
   would add a network round trip to what is meant to be a fast public page - flagging rather than
   fixing.

Verified locally (no browser available to this agent): `cd frontend && npx tsc --noEmit` clean,
`npm test` (33/33 passed), `npm run build` succeeded.

### Coordinator browser verification (2026-08-16) — AC3 and AC4 measured

Run against an isolated stack: a scratch sqlite database and a backend on :8010, deliberately not the
`manage.py runserver` on :8000 that was already on this machine — that one inherits the repo-root
`.env` and so is very likely pointed at production Neon. The proxy target was proved before testing:
the scratch session cookie returns `verify10` through :5199 and is rejected (403) by :8000, i.e. two
different databases.

**AC3, in a fresh browser context with no cookies and no localStorage:**

    GET /public-submit                        -> landed on /public-submit   (no redirect to /login)
    fill "Einladungscode" = VERIFY10CODE, paste a job URL, click "Jobangebot senden"
                                              -> 201 POST /api/public/submit/

and the row it created, read back from the database:

    created_by=None  submitted_for=verify10  source=friend
    visible on the inviting owner's board via access.accessible_jobs(): True
    board count 5 -> 6

**One real failure on the way, worth keeping** because it is the step a reader will hit too. The first
attempt returned **500**, not 400: `OperationalError: no such table: dachapply_cache`. The anonymous
throttle uses `DatabaseCache`, so `public_submit` cannot serve a single anonymous request until
`manage.py createcachetable` has been run against that database. It is not created by `migrate`. On a
fresh environment this route is 500, not "rate limited" — the same footgun the deploy hit.

**AC4, same anonymous context — every anchor and every button on the page:**

    anchors:  DACHApply -> /login,  Login -> /login?mode=login,  Start -> /login?mode=register,
              Privacy -> /privacy,  Terms -> /terms
    buttons:  "☾" (dark mode),  "Jobangebot senden"
    hrefs matching /add /jobs /prompts /import /followups /export /bookmarklet /settings:  []

No authenticated destination, no profile menu, no account avatar.

**A near-miss in the method, recorded because it would have produced a false pass:** the first probe
scoped to `nav a, header a` and returned `[]` for both links and buttons — which reads as "nothing
leaked" but actually meant the selector matched no container at all. Re-running against every `a` and
`button` on the page is what turned an empty result into evidence. An empty result is only evidence
when you have shown the instrument can produce a non-empty one.

<!-- SECTION:NOTES:END -->
