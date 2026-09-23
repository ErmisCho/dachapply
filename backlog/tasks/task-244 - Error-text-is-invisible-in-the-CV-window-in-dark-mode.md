---
id: TASK-244
title: Error text is invisible in the CV window in dark mode
status: Done
assignee:
  - '@pi'
created_date: '2026-09-21 17:00'
updated_date: '2026-09-23 08:40'
labels:
  - frontend
  - ux
  - accessibility
dependencies: []
priority: high
type: bug
ordinal: 243000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found 2026-09-21 while verifying TASK-243, and measured in a browser rather than inferred.

frontend/src/App.tsx:608 renders the compact CV generator popup with 'bg-white text-slate-900' and NO dark: variant, so in dark mode the window stays a white island while the document carries the .dark class. Every .dark rule inside it then styles content for a dark background that is not there.

Measured, ErrorBox in exactly that situation: index.css:14 sets .dark .field-error-message{color:#fecdd3}, which against the window's white gives a contrast ratio of **1.41:1**. AA wants 4.5:1. In practice an error message in that window is close to unreadable in dark mode - and errors are the messages that matter most.

This predates TASK-243 and is not caused by it. It is the reason TASK-243's status messages kept an opaque tone fill instead of going fully transparent: a message that must be legible on BOTH a white island and a dark page has to bring its own background, since no single text colour clears 4.5:1 against both. Fix the surface and that constraint disappears.

Worth checking the same pattern elsewhere while in there: any component with a hardcoded bg-white and no dark variant has the same defect waiting.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 In dark mode, an error shown inside the CV generation window is legible - measured contrast at or above 4.5:1 against the surface it actually sits on, not against the surface it was designed for
- [x] #2 The fix addresses the surface rather than the text: the window gets a dark variant like the rest of the app, instead of each message being patched to survive a white background
- [x] #3 Every message kind in that window is re-measured after the change - error, success and info, compact and full - in both modes
- [x] #4 Once the surface is dark in dark mode, the status-message tone fills are re-evaluated: they were kept opaque in TASK-243 only because the window is white, and the task records whether they can now go transparent
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
## The description's attribution was WRONG. Corrected here rather than quietly edited.

This task was filed saying the popup SHELL (App.tsx bg-white text-slate-900) is a white island in dark
mode, measured at 1.41:1. The number was right for the rig it came from and the conclusion was wrong,
and the implementing agent refused the brief rather than building to it. Re-measured by the
coordinator against the stylesheet localhost:8000 actually serves:

    .dark .bg-white { background-color: rgba(3,7,18,0.9) !important; }   <- exists, and applies

    shell (class bg-white)      paints #030713   error on it   14.28:1   fine
    panel (class bg-white/70)   paints #b3b5b8   its error     1.42:1    FAILS
                                                 field-error   1.46:1    FAILS

The original 1.41 came from a coordinator rig that set the surface with an inline
style="background:#fff" instead of the CLASS bg-white, so the blanket .dark override never applied
and the ratio was then computed against a hard-coded white. That is exactly the mistake this task's
own brief warned the agent about -- compute against the painted ancestor, not an assumed colour --
and the coordinator made it.

**The defect is real, in that window, at that magnitude, on a different element.** The blanket
override matches the literal class bg-white; Tailwind's opacity-suffixed bg-white/70 is a different
class name and slips past it. Two panels inside the CV generation window use it: the correction drop
zone in 'Adjust latest files' (which renders its own image error) and the Adjust-model picker.

AC1 and AC2 stand as written and are satisfied by the fix; only the element they point at changes.

## Fix, and what it deliberately does not do

Two classes, on the surfaces, matching the pattern the Nav account menu and the guided-tour card
already use:

    bg-white/70 p-2           ->  + dark:bg-slate-950/70     (CorrectionInput drop zone)
    bg-white/70 px-2 py-1.5   ->  + dark:bg-slate-950/70     (Adjust-model picker)

No message was recoloured and no popup-scoped override was added, which is AC2. The agent also
declined to add a dark: variant to the shell: .dark .bg-white is !important and beats a utility of
equal specificity, so the class would have looked like a fix while doing nothing. Pinned by a test.

Coordinator-verified: npx tsc --noEmit clean, npm test 279 passed in 18 files (275/17 before, +4 new).
The new tests earn their place -- reverting the two classes turns two of them red, and one is a
general guard that fails on ANY new light surface in src/ that nothing darkens, naming file and line.

## AC4 answered: yes, the TASK-243 fills can go transparent -- but not yet

Measured across 36 combinations with the fills stripped: every single one improves, worst case
7.12:1, comfortably AA. They were NOT removed, for a measured reason rather than caution: two light
islands are still open elsewhere (TASK-245, one of them 1.07:1), and a status message landing on
either with no fill of its own would be unreadable. Removing them is a clean follow-up once TASK-245
lands; the numbers are recorded there so it need not be re-measured.
<!-- SECTION:NOTES:END -->
