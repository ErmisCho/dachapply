---
id: TASK-138
title: The chat bubbles blow the page out sideways
status: In Progress
assignee: []
labels:
  - frontend
  - mailbox
  - ux
dependencies:
  - TASK-134
priority: high
ordinal: 138000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner report 2026-08-19: *"I no longer see the bubble conversations."*

They are rendering. They are just not bubbles any more. Measured in the shipped bundle
(`index-CINSvz2J.js`) at a 1412px viewport, walking up from a message body:

    div  bubble            w 1630   (w-full)
    div  max-w-[85%]       w 1630
    li   flex justify-start w 2203   min-width: auto
    ul   grid gap-2         w 2203
    div  conversation card  w 2246   inside a grid whose own width is 1374
    body                    scrollWidth 2277   vs viewport 1412

Two separate faults, both visible in that one column of numbers.

**1. The page overflows sideways.** `document.body.scrollWidth` is 2277px in a 1412px viewport — the
whole dashboard scrolls horizontally now. A CSS grid item defaults to `min-width: auto`, so it
refuses to shrink below its content's min-content width; `whitespace-pre-wrap` on a message body with
a long unbreakable token (a URL, a signature line) makes that min-content width enormous, and nothing
between the bubble and `<body>` stops it. `min-w-0` is present on the message's own flex column and
nowhere else on the path, so it caps nothing.

**2. Every message is a full-width band.** The bubble carries `w-full`, so it fills whatever width
the blowout hands it regardless of how much text it holds. Measured: a 274-character message renders
970px wide; a 528-character one renders 1630px. A chat bubble is sized by its content — that is the
entire visual language the owner asked for ("blue bubbles", "like a chat application like on
linkedin, whatsapp"). `w-full` is what removed it, and at these widths `justify-end` vs
`justify-start` conveys nothing either, because both sides start at the same left edge.

This is a regression against TASK-134 AC4 and AC9, which are still checked off on the strength of a
narrow-panel screenshot. They were verified in the 384px hover popup, not in the full-width dashboard
panel, where the same components are also mounted.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The dashboard page does not scroll sideways: `document.body.scrollWidth <= window.innerWidth` with the mailbox panel expanded and a long-token message rendered. Measured in the browser at 1412px, since this is the exact measurement that failed — 2277 vs 1412
- [x] #2 The same holds at 360px and 430px, measured by the same-origin iframe technique this repo already uses (TW-004: window resizing does not change the page viewport on this display)
- [x] #3 A long unbreakable token in a message body wraps instead of setting the container's width — a URL or a 200-character run of non-space characters is the real case, and it comes from strangers, so it cannot be assumed absent
- [x] #4 A bubble is sized by its content, not by the container: a short message renders visibly narrower than a long one at the same viewport. Verified by measuring two real messages of different lengths in the same thread and asserting the widths differ
- [x] #5 A bubble never exceeds a readable measure — state the cap chosen and why. 1630px of 12px text in one line is not a bubble and is not readable prose either
- [x] #6 The owner's own messages remain visually distinct and on their own side (TASK-134 AC4), and that distinction is still legible once the bubbles are content-sized — 4 owner messages and 123 from others are on the board today, so both sides exist to check
- [ ] #7 The fix holds in BOTH places these components mount: the full-width dashboard panel AND the 384px hover popup. TASK-134 was verified in the popup only, which is how this shipped
- [x] #8 `npx tsc --noEmit` and `npm test` clean, and any new pure logic lives in `appUtils.ts` with a test, per this repo's standing split
- [x] #9 No new dependency, and no `dangerouslySetInnerHTML` — TASK-134 AC3 stands: a message body is rendered as text, never as markup
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
The blowout is standard CSS grid/flex behaviour, not a Tailwind quirk: every grid and flex item on
the path from the bubble to `<body>` needs `min-w-0` (or an `overflow` that establishes a new
formatting context) or the largest min-content width in the subtree wins. Measured above, the chain
that leaks is `li` (`min-width: auto`) and the conversation card inside `grid gap-3`.

`break-words` alone would fix AC3 and hide AC1 without fixing it — the container would still be
allowed to grow, it would simply have less reason to. Do both, and prove AC1 with the measurement
rather than by reasoning that the wrap makes it impossible.

For AC4, `w-full` is the whole bug; a bubble wants to be sized by its content with a max, not
stretched. Note that `max-w-[85%]` on the flex column is a percentage of a parent that is itself
blown out, so it is not a cap today — it is 85% of 2203px.
<!-- SECTION:NOTES:END -->
