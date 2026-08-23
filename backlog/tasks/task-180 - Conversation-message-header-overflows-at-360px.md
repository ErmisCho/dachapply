---
id: TASK-180
title: Conversation message header overflows at 360px
status: To Do
assignee: []
labels:
  - frontend
  - mailbox
  - ux
  - bug
dependencies: []
priority: medium
ordinal: 180000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found by coordinator measurement while verifying TASK-177, 2026-08-23. Pre-existing; TASK-177 did not
cause it and no longer widens it.

The header row of a conversation message (`MailboxConversationMessage` in `App.tsx`) does not fit at
360px. Measured in the browser on a real 15-message thread, with the message list constrained to
360px:

    label variant                       rows overflowing   worst overflow
    glyph only (the pre-TASK-177 markup)      8 of 15            15px
    word only, no glyph                       8 of 15            33px
    "Show ▸" as TASK-177 first shipped        8 of 15            45px

    at desktop width (2962px container)       0 of 15             0px

TASK-177 shipped a follow-up putting the WORD behind `hidden sm:inline`, so narrow viewports now
render exactly the pre-TASK-177 markup and the aggravation is gone. **The 15px overflow underneath it
is still there and is what this task is about.**

The cause is the header being a flex row of four `shrink-0` children — the avatar badge, the full
date string (`dateStyle:'medium', timeStyle:'short'`, e.g. "Sep 16, 2025, 10:36 AM"), the `n/m`
thread counter, and the state cue — plus a `min-w-0 truncate` sender name that is the only thing
allowed to absorb pressure. Once the sender name has truncated to nothing, the row still exceeds
360px.

The date is the biggest single contributor and the most compressible: a thread whose messages all
arrived this month repeats the year and the full month name on every row.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The header row fits at 360px with no overflow on any row of a 15-message thread — measured, with the before and after numbers stated
- [ ] #2 Measured at a true 360px VIEWPORT, not a constrained container — the previous measurement could not exercise `sm:` media queries, so a container test is not sufficient evidence here
- [ ] #3 The date remains readable and unambiguous at desktop width; if it is shortened at narrow widths, state the format chosen at each breakpoint
- [ ] #4 Sender name, thread counter and the collapse cue all remain present at 360px — fixing overflow by deleting information is not a fix
- [ ] #5 TASK-177's collapsed preview line and TASK-176's bubble width still hold, measured after the change
- [ ] #6 Frontend typecheck and tests green; `localhost:8000` loads the board without an application error after a rebuild in the owner's checkout
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Measurement technique matters here and cost a cycle on TASK-177. This display does NOT honour window
resizing — `window.innerWidth` stays 3072 after a resize to 360 — and the app sends
`X-Frame-Options: DENY`, so the same-origin iframe trick used elsewhere in this repo does not work
against it either. Constraining a container's width exercises flex layout but NOT `sm:`/`md:` media
queries, which key off the viewport. Use browser device emulation, or a real phone, and say which.

Do not fix this by removing `shrink-0` from the cue and letting it truncate — a half-rendered
"Sho…" is worse than the glyph it replaced.
<!-- SECTION:NOTES:END -->
