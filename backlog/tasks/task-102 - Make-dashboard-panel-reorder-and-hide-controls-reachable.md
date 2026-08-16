---
id: TASK-102
title: Make dashboard panel reorder and hide controls reachable
status: To Do
assignee: []
created_date: '2026-08-16 14:30'
labels:
  - frontend
  - accessibility
dependencies: []
priority: medium
ordinal: 103000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`DashboardPanel`'s move-left / move-right / hide controls are `hidden group-hover:flex`. Because
`display:none` removes them from the tab order entirely, `group-focus-within` can never fire from
inside them either — so they are unreachable by touch **and** by keyboard, with no alternative path.

Found while implementing TASK-81, which fixed exactly this class of bug for the three disclosures
its AC3 names (the analyze per-job picker, the batch source-text preview, and the match-gap popup).
These panel controls are the same defect and were deliberately left alone rather than quietly
widened into that task's scope: fixing them needs a new affordance, not a `useDismiss` call, because
there is no trigger to attach to — the controls *are* the hover-revealed thing.

There is a partial workaround today: the "Panels" menu (which TASK-81 did make keyboard-operable)
can hide and show panels. Reordering has no non-pointer path at all.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Panel reorder and hide are operable by keyboard alone, verified by an actual keyboard-only walkthrough recorded in the closing notes
- [ ] #2 The same controls are operable by tap on a touch device, with a target of at least 44px
- [ ] #3 Desktop hover behaviour and panel density are not degraded for pointer users
- [ ] #4 No new axe violations on the dashboard
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
A per-panel menu button (always visible, `aria-expanded`, wired to the existing `useDismiss` hook
from TASK-81) containing Move left / Move right / Hide is the smallest thing that satisfies all four
criteria — it gives a real trigger, a real tab stop and a real tap target, and reuses machinery that
already exists rather than adding a second dismissal mechanism.

Keeping the hover controls as a pointer-only shortcut alongside it is fine and covers AC3; they just
must not be the only path.
<!-- SECTION:NOTES:END -->
