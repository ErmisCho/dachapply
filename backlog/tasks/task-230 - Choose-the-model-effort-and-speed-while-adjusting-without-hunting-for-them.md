---
id: TASK-230
title: 'Choose the model, effort and speed while adjusting, without hunting for them'
status: To Do
assignee: []
created_date: '2026-09-11 11:20'
updated_date: '2026-09-11 20:08'
labels:
  - frontend
dependencies: []
priority: high
ordinal: 229000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner request 2026-09-11. When adjusting a CV or letter, the model and speed should be selectable there.

The backend already supports it: the readjust call sends provider, model, effort and speed, exactly as generation does (App.tsx:587, `readjust()` body). Nothing server-side is missing.

The problem is reachability, and TASK-228 caused half of it. That task collapsed the model cluster (Provider, Model, Effort, Speed) into one `<details>` and the readjust controls into a different one, so while the adjust section is open the model controls are closed and out of sight. Both also read the SAME state, so changing the model for an adjustment silently changes it for the next generation too - which may or may not be wanted and should be decided rather than inherited.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The model, effort and speed that a readjustment will use are visible and changeable from the adjust section itself, without collapsing or scrolling to a different part of the popup
- [ ] #2 What the readjustment actually ran with is evident from the UI before it is started - not only after, and not only in the request payload
- [ ] #3 It is a deliberate, recorded decision whether the adjust model selection is shared with generation or separate from it, and the UI makes whichever was chosen obvious
- [ ] #4 Frontend tests cover the control, and the result is verified in the served bundle at localhost:8000
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
## Decision, owner, 2026-09-11: a SECOND picker

AC3 asked for a deliberate choice between sharing the model selection with generation and giving the
adjust path its own. The owner chose **separate**: adjusting gets its own model, effort and speed,
independent of what generation is set to.

Consequence to design around rather than discover: a second picker ADDS height, and TASK-233 now has a
hard fit target. So the two pickers cannot both be four stacked labelled selects - whatever form the
model cluster takes has to be compact enough to appear twice.
<!-- SECTION:NOTES:END -->
