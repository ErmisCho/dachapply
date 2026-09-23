---
id: TASK-247
title: Two text colours sit just under AA on the surfaces they actually land on
status: To Do
assignee: []
created_date: '2026-09-23 09:03'
labels:
  - frontend
  - accessibility
dependencies: []
priority: medium
type: bug
ordinal: 246000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Both found while fixing TASK-244 and TASK-245, both deliberately left alone at the time because they are a different shape: the surface is fine, the text colour is marginal.

1. Stale board row (isStaleStatus / isStaleUnapplied, the sibling branch to the archived row on the same line in App.tsx around 558): bg-slate-100 with text-slate-500 measures **4.34:1 in light mode**, under the 4.5 AA threshold. Dark mode is covered at 6.91.

2. A bare ErrorBox on the light page background: #e60023 on the body::before gradient's #f3f6fe measures **4.43:1**. It only bites on the gradient itself - inside any card or window the same text reads 4.70-4.78.

Neither is invisible, and neither is urgent in the way the 1.07:1 export popup was. They are recorded because both were measured rather than guessed, and because the next person to touch those colours should know how little headroom is left: text-slate-500 on that tint computes to 4.47, so a single shade in the wrong direction drops it under.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Each case measures at least 4.5:1 against the composited surface it actually renders on, in the mode where it currently fails
- [ ] #2 The fix is to the failing pair, not a blanket colour change - the other surfaces each colour lands on are re-measured to show none regressed
- [ ] #3 The darkSurfaces guard is extended to whichever case is fixed, and reverting the fix turns the suite red
<!-- AC:END -->
