---
id: TASK-134
title: Make the conversation read like an email thread
status: In Progress
assignee: []
labels:
  - frontend
  - mailbox
  - ux
dependencies:
  - TASK-130
  - TASK-132
priority: high
ordinal: 134000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner report 2026-08-19, using the conversation view on their real mail. Five things, all about the
same complaint: it displays messages, it does not read like a thread.

1. **Text cannot be selected.** The owner wants to copy a sentence out of a reply and cannot.
2. **`&nbsp;` and friends show as literal text.** Measured: **44 of 598** stored bodies contain raw
   HTML entities. They render as `the&nbsp;Senior Software Engineer` instead of a space.
3. **It is not obvious the messages belong to one exchange.** They are stacked cards with no visual
   sense of a thread.
4. **"Recruiter reply" is not a natural label** for what the badge marks. The owner suggested
   `Thread (1/x)` where x is how many messages the app has captured for that position — a position in
   the conversation, which is what someone actually wants to know.
5. **"Reply in Gmail" is a link buried under the body** when it wants to be a button in the message's
   own header, next to that badge.

None of this is about missing data — the bodies, senders, dates and `sent_by_owner` flag are all
there since TASK-132. This is the rendering.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The text of any message in the conversation can be selected and copied with the mouse — verified by actually selecting text in a browser, since the likely cause is a click handler or `select-none` on an ancestor rather than anything visible in the markup
- [x] #2 HTML entities render as the characters they stand for: a body containing `&nbsp;`, `&amp;`, `&#39;` shows a space, an ampersand and an apostrophe. Verified against one of the 44 real messages that contain them, not a synthetic string
- [x] #3 Decoding entities does not introduce an injection route: a body containing `<script>` or `<b>` renders as literal visible text, never as markup. Asserted by test — this is the one place where "make it look like email" and "never execute what a stranger sent me" pull against each other
- [x] #4 A reader can tell at a glance that the messages are one exchange, and who spoke: the owner's own messages (`sent_by_owner`, stored since TASK-132) are visually distinct from the other party's
- [x] #5 The classification badge is replaced by the message's position in the conversation — `Thread (2/7)` style, where the denominator is how many messages the app has captured for that job. Where the classification still matters (a blocked draft, an uncertain message), it is still reachable, not silently dropped
- [x] #6 "Reply in Gmail" is a control in each message's header row rather than a link below the body, and it still opens that specific message's thread
- [x] #7 `npx tsc --noEmit` and `npm test` clean; the entity-decoding is a pure function in `appUtils.ts` with tests including the injection case
- [x] #8 The subject is shown ONCE per email thread, not repeated on every message in it — owner report 2026-08-19: their zooplus job contains two distinct threads ("Feedback on your application…" and "Your follow-up interview…"), and the subject repeating on all seven rows is what made the view unreadable
- [x] #9 Messages within a thread are laid out as a conversation, the way a chat application does it: who spoke and when shown lightly rather than as a header block per message, and the owner's own messages visually on their own side. `thread_id` is populated on all 653 rows since TASK-132's backfill, so grouping by thread is available and does not need inventing
- [x] #11 The message header reads as discreet metadata, not as a heavy control bar: owner report 2026-08-19 on the shipped chat layout — the dark pill carrying `Julia Barylak from zooplus SE <notifications@join.zooplus.com> · 6/18/2026, 1:48:14 PM · 3/5 · ▼` is louder than the message it labels. Sender, time and position should sit quietly under the bubble's own styling
- [x] #12 "Reply in Gmail" is an icon-only control inside that header, not a worded link — and it keeps an accessible name, because an icon with no label is unusable by screen reader and unguessable by everyone else. This repo has filed two tasks (TASK-81, TASK-102) about controls that looked fine and were unreachable
- [x] #13 The full email address is not shown in the header when a display name exists — `Julia Barylak` is what identifies the sender; `<notifications@join.zooplus.com>` is noise that pushes the timestamp off the line. The address stays available (title, or the expanded view), never simply discarded
- [x] #14 Messages inside a thread run oldest at the top to newest at the bottom, the way a chat application reads — owner instruction 2026-08-19. This inverts the current "newest first" ordering, which the thread heading currently states out loud, so the heading has to change with it. The per-job endpoint returns newest-first (`received_at` desc, nulls last), so the reversal is the view's job; note that `received_at` is nullable and the fallback must stay deliberate rather than letting nulls drift to an arbitrary end
- [x] #15 The proposed decision and the drafted reply sit BELOW the conversation, not above it — owner instruction 2026-08-19. Once the thread reads oldest-to-newest (AC14), the draft is the next thing in that conversation, so it belongs where a chat puts its compose box. Currently they render above the messages, which asks the owner to decide before reading
- [x] #10 A job containing more than one thread keeps them visibly separate — the seven zooplus messages are two conversations, and merging them into one stream would be a different lie from the current one
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-08-20 close-out (evidence: backend suite 783 green; browser measurements on the built bundle at localhost:8000; prod-DB reads and app-command runs with the owner's approval; merges #51/#52/#53 live with HTTP 200): #1 stays unchecked for one human gesture: every measurable precondition is fixed and measured - computed user-select:text on the body chain (was none via Chrome's UA [draggable] rule, fixed in #52), -webkit-user-drag:none on the card, and no dragstart hijack observed - but this rig's pointer input drops mousedown entirely (capture listeners recorded only mousemove on two drags and a double-click), so an actual drag-selection needs one human hand. #2 measured: stored 'Hi Ermis,&nbsp;' renders as a real space. #11 measured: header computes transparent background at 11px.

AC1's likely cause is the expand/collapse control: if the whole message is inside a `<button>`, or an
ancestor carries `select-none` (the board table does, deliberately, for shift-click range selection),
text cannot be selected. The fix is to make the header the button and leave the body outside it.

AC3 is the one to get right rather than fast. The safe shape is: decode entities to text, then render
that text as TEXT (React escapes by default) — never `dangerouslySetInnerHTML`. If a later task wants
real HTML mail rendered, that needs sanitising and is its own task with its own argument; do not open
that door here by accident.

AC5's denominator is per job, and the number the owner sees must match what the app actually has —
if a thread was capped during ingestion (`INGEST_THREAD_MESSAGE_CAP`), saying `2/7` when 40 exist in
Gmail is a lie the owner cannot detect. Either say what is captured and label it as such, or count
honestly.
<!-- SECTION:NOTES:END -->
