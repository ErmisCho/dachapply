---
id: TASK-82
title: Cache the session auth check to stop route-change blanking
status: Done
assignee:
  - '@claude'
created_date: '2026-08-16 00:43'
updated_date: '2026-08-16 13:10'
labels:
  - frontend
  - performance
  - ux
dependencies: []
priority: medium
ordinal: 87000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Every protected route is individually wrapped in RequireAuth (frontend/src/App.tsx:213), which runs `api('/auth/me/')` on mount and renders a full-page "Loading…" until it resolves (App.tsx:89). Every internal navigation therefore flashes a blank page and serializes an extra network round-trip before the destination page's own data fetch can even start.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Navigating between protected routes performs no repeated /auth/me/ round-trip once authenticated, verified in the browser network log
- [x] #2 No full-page loading flash on internal navigation
- [x] #3 A 401 from any API call still routes to /login as today, and logout invalidates the cached check
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
A module-level promise (or context) caching the first /auth/me/ result for the session is enough; invalidate on logout and on any 401. No state library.

### Closing notes (2026-08-16)

Not in the original wave plan — TASK-82 appeared in no wave and no owner-checklist item, so the
executing coordinator slotted it into Wave 3 and recorded the deviation in the plan file.

`api/client.ts` now memoises the first `/auth/me/` promise and its resolved user. `RequireAuth`
seeds its state **synchronously** from the cached user, which is what removes the flash — resolving
through `.then` alone would still have painted one `Loading` frame.

AC1 measured with the network log across a six-hop tour using only real in-app links:

    6 client-side hops -> 0 full document loads, 0 /auth/me/ requests

(An earlier attempt reported 2 calls; that was the harness, not the app — routes reached by
synthesising an `<a>` element do a full document load and legitimately re-check.)

AC2 measured with a MutationObserver counting frames in which a full-page "Loading" was on screen
during the same tour: **0**.

**AC3 initially failed, and the first fix attempt would have hidden it.** With a warm cache, killing
the session server-side and navigating produced six 401s and left the user sitting on the board:

    warm cache, session dies, client-side nav -> url=/  STAYED     (before)

The cause is that the 401 guard cleared the cache correctly, but `RequireAuth`'s effect had `[]`
deps, so nothing re-checked on the next route. A fresh document load *did* redirect, which is
exactly the kind of partial evidence that makes a broken criterion look met.

The fix is one dependency: `useEffect(…, [loc.pathname])`. When the cache is warm `authMe()` returns
the memoised promise, so this costs no network call and AC1 still holds; once a 401 has cleared the
cache it re-checks and redirects. Re-measured:

    fresh load, dead session            -> /login   (401 /api/auth/me/)
    warm cache, dies, client-side nav   -> /login   (401 /api/auth/me/)
    6-hop tour, healthy session         -> 0 /auth/me/ requests, 0 Loading frames
    logout                              -> /login, cache emptied

Cache invalidation points, all present: Nav logout, account deletion, login/register success, demo
login, a 401 inside `api()`, a 401 inside `downloadApi()`, and the two raw `fetch` calls in Export
that bypass `api()`. A failed `/auth/me/` is also not cached, so a transient failure retries instead
of pinning the user to `/login`.
<!-- SECTION:NOTES:END -->
