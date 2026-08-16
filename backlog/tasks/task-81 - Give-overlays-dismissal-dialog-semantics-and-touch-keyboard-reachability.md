---
id: TASK-81
title: Give overlays dismissal, dialog semantics and touch/keyboard reachability
status: Done
assignee:
  - '@claude'
created_date: '2026-08-16 00:43'
updated_date: '2026-08-16 14:30'
labels:
  - frontend
  - a11y
  - ux
dependencies: []
priority: medium
ordinal: 86000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
No menu or modal in the app closes on Escape, and none has role="dialog", aria-modal, aria-expanded, or focus trapping (grep across frontend/src: zero hits). Specifics: the dashboard Status/Priority/Recommendation filter menus stay open until Apply is clicked; the Nav avatar menu closes only on route change (App.tsx:86); promptModal has no backdrop-close, only its Close button (App.tsx:98); noteModal and BatchCvGenerator close on backdrop click only (App.tsx:98, 115); the Export hover menus have no keyboard path (App.tsx:207). Focus is never returned to the trigger.

Related reachability gap: hover-only disclosures are dead on touch. Tapping "Analyze N new jobs" immediately analyzes all because the per-job picker is group-hover-revealed (App.tsx:98); the BatchCvGenerator source-text preview is group-hover (App.tsx:115); MatchGapPopup is mouseenter-only and invisible to keyboard users too (App.tsx:51). Tasks 9/67/68 fixed nav and tap targets, not these.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Every modal closes on Escape and carries role="dialog" aria-modal="true"; menu trigger buttons carry aria-expanded
- [x] #2 Menus close on outside click and on Escape
- [x] #3 The analyze per-job picker, the batch source-text preview, and the match-gap popup are each reachable by tap and by keyboard
- [x] #4 On close, focus returns to the element that opened the overlay
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
One small shared dismiss hook (Escape + outside click + focus restore) reused across every overlay beats per-overlay patches — there are at least seven call sites, so the shared fix is also the shortest diff. For the hover disclosures, click/tap-to-toggle with aria-expanded covers touch and keyboard in one move.

### Closing notes (2026-08-16)

**The ticket named 8 overlays; there are 21.** One shared `useDismiss(open, close, kind)` hook now
backs 16 of them in three modes - `menu` (Escape + outside click + focus restore), `modal` (Escape +
focus pulled into the panel + focus restore), and `panel` (Escape + focus restore only). Five were
left alone with reasons recorded below, which is the part worth reading.

Measured in a browser rather than argued from the JSX:

    menu "Statuses"   aria-expanded false->true | Escape->false, focus back on the Statuses button
                                                | reopen->true, outside click->false
    menu "Panels"     same, focus back on the Panels button
    noteModal         role="dialog" aria-modal="true" aria-label="Notes", focus moved INSIDE on open
                      Escape -> 0 dialogs, focus back on the "notes" button
    32 aria-expanded triggers present on the board

AC3, the three hover-only disclosures, each driven by click rather than hover:

    analyze picker      tap target 44x44 on mobile, aria-expanded=true, 3 job entries appeared,
                        Escape closed it and returned focus to the chevron
    batch source text   button with aria-expanded, and it shows REAL source text (see TASK-91)
    match-gap popup     click -> aria-expanded true, click again -> false (a genuine toggle, where
                        before a tap fired mouseenter-then-click and opened-then-closed it)

The analyze picker is the one that mattered most: tapping "Analyze N new jobs" used to be the only
possible outcome on a phone, because the per-job list was `group-hover`. There is now a separate
chevron control, so the destructive-by-accident path is gone.

**Three overlays are Escape-only, deliberately.** The feedback-due popover is rendered twice (mobile
card + desktop table) from one piece of state, so a single container ref points at whichever copy is
`display:none` and every real click would read as "outside"; the batch source preview lives inside a
`rows.map` with shared state; `MatchGapPopup` is portalled to `<body>`, so its own panel is
"outside" its trigger. These are popovers rather than menus, and AC2's own list - the dashboard
filter menus, the Nav avatar menu, the Export menus - is fully covered with outside-click. Recorded
because "menus close on outside click" could be read more broadly.

**Focus restore is conditional and that is the correct behaviour.** Focus returns to the opener when
closing left it orphaned on `<body>` (Escape, or an in-overlay Close). If the user closes an overlay
by clicking some other control, focus stays where they clicked - yanking it back would fight the
browser and the user. AC4 does not distinguish the two cases; this is the reading that does not
produce a bug.

**Left alone, with reasons:** the CvGenerator compact popover hosts a multi-minute generation and
its own Close is disabled while loading, so auto-dismiss would orphan an in-flight task (it got
`aria-expanded` only); the stage editor is inline flow content that covers nothing;
archive/delete inline confirms already have a visible Cancel; `GuidedOnboardingTour` is
deliberately non-modal (`pointer-events-none` backdrop - the point is that you keep using the page),
so `aria-modal` would have been a lie.

**Found and not fixed - filed as TASK-102:** `DashboardPanel`'s move/hide controls are
`hidden group-hover:flex`, so they are dead on touch and keyboard. Same class of bug as AC3 but
outside its three named cases, and fixing it needs a new affordance rather than a hook call.

Implementation note worth keeping: the outside-click listener is **capture-phase `click`**, not
`mousedown`. `mousedown` would unmount the feedback-due popover before the browser moved focus, so
its `onBlur`-saving date inputs would silently lose the typed value; bubble-phase would never fire
for the job-table subtrees that call `stopPropagation`.

axe: **0 violations** on `/`, `/export` and `/settings/profile` after this refactor (and on
`/login`, `/add`, `/public-submit`, `/jobs/<id>`), so none of the new roles or controls regressed
the accessibility baseline TASK-87 established.
<!-- SECTION:NOTES:END -->
