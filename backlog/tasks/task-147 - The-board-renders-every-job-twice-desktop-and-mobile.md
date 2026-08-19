---
id: TASK-147
title: The board renders every job twice, desktop and mobile
status: In Progress
assignee: []
labels:
  - frontend
  - performance
priority: medium
ordinal: 147000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found while measuring TASK-142, and deliberately kept out of it — different component, different
cause, and folding it in would have let TASK-142 claim a number it did not earn.

TASK-142 set a target of under 10,000 DOM nodes for the whole board page. After that work the page
measures **14,389**, and the mailbox panel is no longer why:

    mobile cards    7,374 nodes    <- all 74 jobs
    board table     4,684 nodes    <- the same 74 jobs
    mailbox panel   1,729 nodes    (was 22,543 before TASK-142)
    ------------------------------
    total          14,389

**12,058 of 14,389 — 84% of the page — is the same 74 jobs rendered twice.** The desktop `<table>`
and the mobile `<article>` cards are both fully populated in the DOM at every viewport, with only CSS
deciding which one is visible. Nothing is virtualised and nothing is conditionally mounted.

This is pre-existing and predates the mailbox work entirely. It was invisible while the mailbox panel
was contributing 22,543 nodes on its own.

Related measured detail, and evidence the pattern is deliberate rather than accidental: each job's
status control renders twice too — 74 `select.mobile-status-select` plus 74 `select.w-24`, 148
selects carrying 1,628 `<option>` elements between them.

### Why this is worth a task rather than a shrug

74 jobs is a small board. The owner adds leads continuously, and this cost is linear with a factor of
two: at 300 jobs the same page is roughly 49,000 nodes before any panel is counted. The freeze
TASK-142 fixed will come back, from a different direction, and the next person measuring it will find
a page that was always like this.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Only one of the two row renderings is in the DOM at a time: measured at 360px, 430px and desktop, the count of `[data-job-row]` elements equals the number of visible rows, not twice it. 148 for 74 jobs is the number to beat
- [x] #2 Total board DOM nodes drop below 10,000 with the mailbox panel present — TASK-142's original target, which this task is what actually reaches. 14,389 is the number to beat
- [x] #3 The board still works at every breakpoint after the change: the desktop table and the mobile cards each render and are interactive at their own widths, verified by measurement at 360px, 430px and desktop rather than by reading the CSS
- [x] #4 Switching breakpoint does not lose state that the owner can see — selection, expanded rows, and the saved sort survive a resize across the breakpoint, since a conditionally-mounted tree unmounts on the way through
- [x] #5 `[data-job-row]` keeps working for TASK-146's click-through-to-a-job navigation, which currently depends on picking the visible copy of a duplicated row (`offsetParent !== null`). If there is only one copy, that selector gets simpler, not broken — verified by actually navigating from the feedback pane
- [x] #6 No new dependency: a virtualisation library is not the answer to a duplicate render, and the shortest fix is not to render the invisible half
- [x] #7 `npx tsc --noEmit` and `npm test` clean; the existing suite passes unchanged
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-08-19, measured in Chrome against the built bundle at localhost:8000: the board now mounts ONE
tree via useMatchMedia('(min-width: 1024px)') — the real breakpoint is lg:/1024px, not the md: this
file guessed. AC1: [data-job-row] count == job count at every width (88 table rows desktop, 88 cards
at 360/430 under the all-status filter; 74/74 under the default filter; never 2x — status selects
88+0, was 74+74). AC2: 6,300 total nodes on desktop with the EMAIL DECISIONS panel present, against
a board that has since grown to 88 jobs (target <10,000, was 14,389 at 74 jobs); 9,864 at 360/430.
AC3/AC4: switching 1275->427->1275 unmounts/remounts the right tree with row selection intact both
ways and the card status select interactive. Caveat worth recording: Chrome does not deliver resize
or matchMedia-change events inside same-page iframes (matches flips, zero events), so the hook also
re-checks on window resize, and the iframe measurement drove that handler explicitly; toplevel
windows deliver both events normally. AC5: feedback-pane click-through scrolled 0->7161, the single
row copy centered (top 786 of 1634), data-scrolled-to set, selection applied. AC6: package.json
untouched. AC7: tsc clean, 104 tests (was 100).

The likely current shape is two sibling trees with `hidden md:table` / `md:hidden` style classes. The
smallest honest fix is to mount one of them, driven by a matchMedia hook, rather than to render both
and hide one — and AC4 exists because that change introduces an unmount that a CSS-only approach never
had.

AC5 matters because TASK-146 already built on top of this bug: its navigation queries all
`[data-job-row]` elements and filters by `offsetParent !== null` precisely because each row exists
twice. That filter is correct today and must not silently start selecting nothing.

Do not solve this by capping how many jobs the board shows. The owner has 74 and wants to see them;
the problem is that each one costs double, not that there are too many.
<!-- SECTION:NOTES:END -->
