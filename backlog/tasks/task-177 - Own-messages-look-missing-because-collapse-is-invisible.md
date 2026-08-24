---
id: TASK-177
title: Own messages look missing because collapse is invisible
status: Done
assignee: []
labels:
  - frontend
  - mailbox
  - ux
  - bug
dependencies:
  - TASK-176
priority: high
ordinal: 177000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner, 2026-08-23: *"I don't see my own emails in the conversation threads now."*

Nothing is missing. The messages are collapsed, and the only thing saying so is a one-character
triangle next to the timestamp.

**Measured on the owner's own board, all conversations expanded:**

    message rows rendered                44
    rows that are the owner's own        18
      rendered WITH a body bubble         3   (marked `v`)
      rendered WITHOUT a body bubble     15   (marked `>`)

    Y You - Sep 16, 2025, 10:36 AM - 2/4  >     no bubble
    Y You - Sep 16, 2025,  3:08 PM - 4/4  v     740-char bubble

Data and API are both fine, verified before touching the UI:

    messages sent by owner, stored        62
    of those with an empty body            0   (0%)
    /api/jobs/462/mailbox/ returns        15 messages, 6 of them the owner's, bodies 740 and 909 chars

So this is purely presentation. The header row renders, the body does not, and the affordance that
would explain why is a `>` glyph among a date, a counter and two icon buttons.

**This is the same defect as the owner's other report on the same screen** (*"there is too much white
space between the threads"*, TASK-176). The white space they circled is where the collapsed bodies
would be. TASK-176 widened the bubbles, which helps the messages that DO render; it cannot help a
message that renders no bubble at all.

**Why collapsing the owner's own messages is the wrong default anyway.** In a mail thread the reply
you sent is half the exchange — it is what makes the recruiter's next message legible. TASK-132
widened this database specifically to store the owner's sent mail so that "a conversation reads as an
exchange instead of one side of it", and defaulting that side to collapsed undoes the point of it.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A message's collapsed/expanded state is obvious without decoding a single glyph — state what the affordance is and where it sits
- [ ] #2 Whatever the default becomes, a reader can tell at a glance that a collapsed message EXISTS and has content, rather than seeing an empty row
- [ ] #3 The owner's own messages are not collapsed by default while received messages are expanded — either both default the same way, or the difference is deliberate and stated
- [ ] #4 Measured before and after on a real conversation: rows rendered, rows with a body, and the vertical white space between the first and last message of a thread
- [ ] #5 Expanding and collapsing still works, and the state survives scrolling within the conversation
- [ ] #6 Verified at desktop width and at 360px
- [ ] #7 TASK-134's drag-select and TASK-176's bubble width still hold, measured after this change
- [ ] #8 Frontend typecheck and tests green; `localhost:8000` loads the board without an application error after a rebuild in the owner's checkout
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Check whether the collapse is per-message state or derived from something like `sent_by_owner` or
message length — the 3 expanded rows out of 18 suggest a rule rather than a user action, since the
owner reports never having collapsed anything.

Do not simply expand everything unconditionally without measuring AC4. A 26-message thread with every
body expanded is its own readability problem, which is presumably why collapsing exists at all. The
defect is that collapse is invisible, not that collapse exists.
<!-- SECTION:NOTES:END -->
