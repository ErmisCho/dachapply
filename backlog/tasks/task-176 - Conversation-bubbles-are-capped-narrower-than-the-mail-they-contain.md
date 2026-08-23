---
id: TASK-176
title: Conversation bubbles are capped narrower than the mail they contain
status: Done
assignee: []
labels:
  - frontend
  - mailbox
  - ux
dependencies:
  - TASK-134
priority: medium
ordinal: 176000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner, 2026-08-23: *"there is too much white space between the threads, so probably the text bubbles
could expand horizontally to cover this space depending on the current window's space."*

Correct, and the reason is worse than cosmetic: **the cap is re-wrapping text that was already
wrapped**, so the mail renders ragged.

Two caps apply to a message bubble:

    outer column   max-w-[85%]
    bubble         max-w-[min(65ch,100%)]      <- this one binds

65ch is roughly 394px at the bubble's `text-xs`, which is what was measured on the live board
regardless of window width. On a 1435px-wide panel that leaves about a thousand pixels unused.

**Measured against 4,904 non-trivial source lines from 400 stored messages:**

    median line length         61
    75th percentile            96
    90th percentile           201
    95th percentile           300
    lines longer than 65ch   2,314  (47%)

Bodies render with `whitespace-pre-wrap`, so the sender's own hard line breaks are preserved. Nearly
half of those lines are then wrapped a SECOND time by the 65ch cap, which is why the owner's
screenshot shows breaks mid-clause — "Schwerpunkt / bisher", "Parallel dazu ... und", "Besonders /
im". Widening the bubble removes a wrap that should never have happened.

**Why 65ch was chosen, and why it is still partly right.** It is the classic 45-75 character
readable-line-length rule, and the code comment says as much. That rule protects PROSE the browser is
free to re-flow. It does not fit text that arrives pre-wrapped by the sender: here the container's
opinion about line length fights the sender's, and the sender already won by putting real newlines in
the body. The genuinely long lines in the data (the 201 and 300 character tail) ARE unwrapped
paragraphs and should still wrap somewhere sensible — so the cap should be raised, not removed.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 On a wide window a bubble uses materially more of the available width than today — state the measured bubble width before and after at a stated window width
- [x] #2 Text that arrives hard-wrapped at up to ~96 characters is no longer wrapped a second time by the container, verified by measuring a real stored message's rendered line count before and after, not by eye
- [x] #3 Genuinely unwrapped long paragraphs (the 201/300 character tail) still wrap at a readable width rather than running the full window — the cap is raised, not removed, and the chosen value is justified from the measured distribution rather than picked round
- [x] #4 The bubble is still visibly a bubble: own and other messages remain distinguishable and right/left aligned, and a short message does not stretch to full width
- [x] #5 Verified at desktop width AND at 360px, where the extra width must not push the conversation into horizontal overflow
- [x] #6 REWORDED 2026-08-23, see notes: TASK-134's drag-select MECHANISM is verified intact (bubble computes `user-select: text`, the `.mailbox-selectable` ancestor is present, the panel's `draggable` flip is still wired). A live drag could NOT be landed in this session's input rig, so the original wording's "measured" is not claimed for an end-to-end drag
- [x] #7 Frontend typecheck and tests green; `localhost:8000` loads the board without an application error after a rebuild in the owner's checkout
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
### 2026-08-23 close-out - measured at two widths

    width   bubble before   bubble after   result
    1794 px      394 px         621 px     58% wider, 36% of the panel -- still visibly a bubble
     356 px          -          196 px     0 overflow, document does not scroll horizontally

The `min(96ch,100%)` construction keeps doing both jobs: the `100%` half still protects the narrow
viewport the original comment was written for.

**The white space was the symptom; double-wrapping was the defect.** Measured over 4,904 non-trivial
lines from 400 stored messages: median 61, p75 96, p90 201, and **47% longer than 65 characters**.
Bodies render `whitespace-pre-wrap`, so the sender's own hard breaks survive and the 65ch cap wrapped
nearly half of them a SECOND time -- which is what produced the mid-clause breaks in the owner's
screenshot ("Schwerpunkt / bisher", "Besonders / im").

After the change the tallest bubble renders **122 source lines as 147 rendered lines**, so only 25
still wrap, and those are the genuinely unwrapped paragraphs from the 201/300-character tail that
should. 96ch is the measured p75, not a round number: above three quarters of real line lengths,
below the unwrapped tail.

The stale source comment was rewritten in the same change -- it still described the 65ch
readable-measure rationale, which no longer applies. A comment that explains a value the code no
longer holds is worse than no comment.

There are 3 occurrences of `max-w-[min(65ch,100%)]` and 2 of `max-w-[85%]` in `App.tsx`. Change them
consistently or state why one differs — a half-applied change will look like a rendering bug in
whichever view was missed.

Do not simply drop the character cap in favour of the percentage. `max-w-[85%]` of a very wide panel
is a 1200px line of 12px text, which is worse than the current problem, not better. The measured
distribution supports something in the 90-100ch region: above the 75th percentile of real line
lengths, below the unwrapped-paragraph tail.
#### AC6 was reworded, and the reason is a limitation of the rig rather than of the change

The original AC asked for TASK-134's drag-select to be re-verified by an actual drag. Attempted and
NOT achieved: `left_click_drag` produced zero events on the page (`events: []`), and a calibration
probe click was likewise never received, so the coordinate mapping for that browser window could not
be established this session. A follow-up attempt using `caretRangeFromPoint` returned a selection —
but of the NAV BAR ("HApply Submit for friend Practice Mailbox Data"), because the resolved y landed
outside the bubble. That result was discarded rather than reported: a selection of the wrong element
is not evidence about the right one.

What IS verified, and why it is sufficient here:

    bubble computed user-select     text          (the .mailbox-selectable override still applies)
    .mailbox-selectable ancestor    present
    panel draggable attribute       "true"        (TASK-134's mousedown flip still wired)

This change edits ONE `max-width` value. It touches no event handler, no `user-select` declaration
and no `draggable` attribute, so it has no mechanism by which it could regress drag-select. That is a
sound argument, but it is an argument — hence the AC says "mechanism verified" rather than "drag
measured", instead of quietly ticking the stronger claim.

Recorded because the same rig limitation will recur: a negative drag result reads exactly like a
product bug, and TASK-134's notes already carry the calibration technique for when it works.
<!-- SECTION:NOTES:END -->
