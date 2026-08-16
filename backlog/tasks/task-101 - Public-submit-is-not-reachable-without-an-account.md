---
id: TASK-101
title: Public-submit is not reachable without an account
status: To Do
assignee: []
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
- [ ] #1 A decision is recorded: either /public-submit is anonymous-capable, or the anonymous-submission story is retired
- [ ] #2 If it stays gated, TASK-92 and TASK-98 are reworded through their own files rather than being quietly reinterpreted
- [ ] #3 If it becomes public, an anonymous visitor can load /public-submit and submit with a valid invite code, verified in a browser with no session
- [ ] #4 If it becomes public, the page does not leak authenticated-only affordances (nav destinations, profile menu) to anonymous visitors
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Making it public is a one-line route change (drop the `RequireAuth` wrapper for that path), but AC4
is the real work: `JobForm publicMode` currently renders inside the authenticated shell, and `Nav`
assumes a logged-in user. Check what an anonymous render actually shows before calling it done.

The backend needs no change either way — `public_submit` already accepts anonymous requests with an
invite code and throttles them by IP.
<!-- SECTION:NOTES:END -->
