---
id: TASK-247
title: Two text colours sit just under AA on the surfaces they actually land on
status: Done
assignee:
  - '@pi'
created_date: '2026-09-23 09:03'
updated_date: '2026-09-23 18:47'
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
- [x] #1 Each case measures at least 4.5:1 against the composited surface it actually renders on, in the mode where it currently fails
- [x] #2 The fix is to the failing pair, not a blanket colour change - the other surfaces each colour lands on are re-measured to show none regressed
- [x] #3 The darkSurfaces guard is extended to whichever case is fixed, and reverting the fix turns the suite red
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Preserve the measured root cause in the debug artifact and keep both fixes scoped to their failing pairs.
2. Darken only the stale-row branch and only page-level bare ErrorBox text.
3. Extend darkSurfaces.test.tsx with exact source guards and WCAG contrast assertions for both fixes and unchanged sibling surfaces.
4. Prove each guard by reverting each fix independently, then run frontend tests/build and the backend suite.
5. Obtain Asian Dad PERFECT, commit/push/squash-merge the implementation, then mark TASK-247 Done in a separate post-merge administrative change and squash-merge it.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Root cause recorded before production edits in `.orchestrator/debug/01a0cf79-e5a3-7027-a486-09c20ff606d4-1.md`. Baseline measurements reproduce 4.3439:1 for the stale row and 4.4258:1 for a bare ErrorBox; the existing darkSurfaces guard passes 5/5 and therefore misses both.

Implemented two scoped changes: stale rows use `text-slate-600`; only `main > .field-error-message` uses `#dc0021`, while nested ErrorBoxes retain `#e60023`. Browser DOM inspection against the built Vite stylesheet confirmed light computed values `#475569` on `#f1f5f9`, bare `#dc0021`, nested `#e60023`; dark mode remains `#d4d4d8` on `#18181b` and `#fecdd3` for both ErrorBoxes.

Fresh WCAG measurements: stale row 6.9170:1 light / 11.9870:1 dark; bare ErrorBox 4.7783:1 on the measured `#f3f6fe` pixel and 4.6199:1 on the darkest gradient stop; unchanged nested ErrorBox 4.7848:1 on white and 4.5732:1 on slate-50.

Guard proof: reverting the stale-row class failed `darkSurfaces.test.tsx` (1 targeted failure); removing the page ErrorBox rule failed it twice (selector-count and exact-rule guards). Restored suite: 6/6 targeted, 297/297 frontend tests. Full gates: frontend build passed; backend 1225 passed.

Implementation squash-merged to `main` as `563a8f8` via PR #179 after GitHub `test` and GitGuardian checks passed.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Fixed both marginal AA pairs without widening either colour globally: stale rows now measure 6.9170:1 in light mode, and bare page-level ErrorBoxes measure 4.7783:1 on the reported composited page pixel. Nested ErrorBoxes and sibling surfaces retain their prior colours and remain above AA. The extended darkSurfaces guard fails when either fix is reverted; 297 frontend tests, the production frontend build, and 1225 backend tests passed. Implementation merged in PR #179 (`563a8f8`).
<!-- SECTION:FINAL_SUMMARY:END -->
