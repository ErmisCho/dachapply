---
id: TASK-178
title: Hide notes behind a click on the board
status: Done
assignee: []
labels:
  - frontend
  - ux
dependencies: []
priority: medium
ordinal: 178000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner, 2026-08-23: *"the notes should be hidden by default and shown only when clicked on."*

Notes currently render inline in the job table. They are reference material consulted occasionally,
not a column scanned every time the board is opened, and on a row-dense board they cost vertical
space on every row whether or not the owner is reading them.

This is the same judgement the owner made about the unmatched-mail panel in TASK-174 — a thing that
is useful on demand should not be permanently resident on the screen used for daily decisions. Both
requests share a shape worth stating once: the board is for today's decisions, and anything else
earns its place by being asked for.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Notes are not rendered inline by default; a row shows an affordance indicating a note exists rather than the note's text
- [ ] #2 A row with NO note is visually distinguishable from a row with an unread note — the affordance must not appear on rows that have nothing behind it
- [ ] #3 Clicking reveals the note without leaving the board and without a page navigation
- [ ] #4 Editing a note still works from the revealed state, with no loss of any editing capability that exists today
- [ ] #5 Measured: board table height and per-row height before and after, on a stated number of rows, so the space actually reclaimed is a number rather than an impression
- [ ] #6 Verified at desktop width and at 360px, where the board renders a card layout rather than a table
- [ ] #7 The first row stays fully visible and clickable (TASK-165) and the table still scrolls horizontally (TASK-139), both re-measured
- [ ] #8 Frontend typecheck and tests green; `localhost:8000` loads the board without an application error after a rebuild in the owner's checkout
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
## Coordinator measurement, 2026-08-24 — the premise above is WRONG

Measured on the owner's own board at localhost:8000 before dispatching anyone, and against the
production database. Recorded rather than quietly fixed, because the brief's opening sentence is what
the acceptance criteria were written from:

- **Notes do NOT render inline.** All 69 visible rows render a `notes` BUTTON (`title="Notes"`,
  `text-[10px] text-slate-400`) that opens a modal. No note prose is on the board. **AC1 is already
  satisfied** and must be verified, not rebuilt.
- **The row height difference is not notes.** Rows measure 78px (43 of them) and 102px (14); the tall
  ones are carrying a `Stale lead` badge, not a note. The notes button is 17px inside a line that
  exists anyway.
- **AC5 cannot be satisfied as written.** There is no inline note text to remove, so the space
  reclaimed by hiding it is **zero**. The honest measurement is the one AC2 implies instead: the
  affordance disappearing from the 57 rows that have nothing behind it.
- **AC2 is the whole real defect.** All 69 buttons are byte-identical -- same classes, same title, no
  variant -- while only **12 of the owner's 83 jobs** carry a non-empty `general` note. The board
  currently claims every job has notes.
- **AC2 needs a backend change, so this is not a frontend-only task.** `/api/jobs/` exposes
  `interview_note` and nothing about general notes; the modal fetches `/jobs/<id>/notes/` per job.
  The list response cannot tell the board which rows have notes. TASK-126 already solved exactly this
  for the mail indicator: `has_mailbox_history`, a serializer boolean sourced from an `Exists()`
  annotation added in `JobLeadViewSet.get_queryset()` -- explicitly chosen over a per-row request.
  Follow that, do not invent a second pattern.

Incidental, not this task: job 450 carries the same general note twice.

## Owner decision, 2026-08-24 — supersedes the 2026-08-24 "expand inline" choice

The earlier choice (indicator, click expands the note in place) was made while the brief's premise was
believed true. Once the measurement above showed notes are ALREADY behind a click, and behind a modal
that already reads and edits them, the owner was asked again with the corrected facts and chose:

**Indicator on rows that have a note; hovering shows the note's first line; clicking still opens the
existing modal for the full read and edit.**

This is a change of brief made BEFORE implementation, not a criterion relaxed after seeing output.
Recorded here and in the sealed rubric's supersession block rather than by editing the original
criterion, per TW-005.

Consequence: the list API must return a short preview string, not a boolean. One field,
`note_preview`, first line of the non-empty `general` note truncated at 140 characters to match
`messagePreviewLine` (frontend/src/appUtils.ts, TASK-177), empty string when there is no note. The
frontend derives "has a note" from non-empty, so there is deliberately no second boolean field.


The board already has a row-level popup pattern (the feedback editor) and it is the wrong one to copy
verbatim: TASK-173 exists precisely because that popup is a non-portalled absolutely-positioned child
of the table's scroll wrapper, which is what blocks TASK-167. If notes need a popup, portal it, or
land TASK-173 first and follow whatever pattern that establishes. Do not add a second popup with the
same clipping problem.

AC2 matters more than it looks. Hiding the text is only an improvement if the owner can still see
WHICH jobs have notes — otherwise the feature becomes invisible rather than tidy, and they have to
click every row to find out.
<!-- SECTION:NOTES:END -->
