---
id: TASK-67
title: Reach nav destinations on mobile
status: To Do
assignee: []
created_date: '2026-08-15 21:05'
labels:
  - frontend
  - mobile
  - ux
dependencies: []
priority: medium
ordinal: 72000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The primary nav link row in `Nav()` (frontend/src/App.tsx) is `hidden ... sm:flex`, so below 640px the Submit-for-friend, Data, Bookmarklet and Profile destinations disappear with no hamburger or drawer replacing them. There is no mobile route to those pages except whatever CTA a given page happens to expose.

Nothing is completely unreachable today, which is why no acceptance criterion was blocked during the TASK-9 verification: the dashboard has its own always-visible "+ Submit link" CTA, and the profile dropdown (the avatar button, visible at every width) still reaches Account settings and, since TASK-8, Send feedback. But Data, Bookmarklet and Profile have no mobile entry point at all.

Surfaced 2026-08-15 while verifying TASK-9 and implementing TASK-8. TASK-8's feedback link was deliberately placed in the profile dropdown as well as the nav row specifically to work around this, which is a workaround rather than a fix.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Every destination in the desktop nav row is reachable below 640px without relying on a page-specific CTA
- [ ] #2 The mobile affordance is keyboard reachable and closes on route change, matching the existing profile dropdown behaviour
- [ ] #3 The desktop layout at 640px and above is unchanged
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
The cheapest fix that satisfies AC1 is probably to extend the existing profile dropdown rather than build a hamburger: it is already rendered at every width, already closes on `loc.pathname` change, and already holds Account settings and Send feedback. Adding the four missing links there is a handful of characters and no new component. Weigh that against a real hamburger before building one.

Whatever is chosen, mind TASK-68: `.nav-link` is `px-1.5 py-0.5 text-[11px]`, roughly a 20px tap target, so simply revealing the existing links on a phone would produce controls that are hard to hit.
<!-- SECTION:NOTES:END -->
