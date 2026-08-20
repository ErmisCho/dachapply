---
id: TASK-155
title: A job's email history lists subjects but cannot be read
status: To Do
assignee: []
labels:
  - frontend
  - mailbox
  - bug
dependencies:
  - TASK-126
  - TASK-152
priority: high
ordinal: 155000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found 2026-08-20 while verifying TASK-152 AC6 on the deployed site.

TASK-126 made a job's email history reachable again after its decisions are made: the board row's
indicator opens a popup listing every message matched to that job. Measured on job 34 (Hays), that
popup renders **30 list items and 0 message bodies** — `[id^="mailbox-msg-body-"]` count is zero,
and there are no expand controls (`button[aria-controls]` count is zero). Each row shows subject,
thread position, sender, date, a "Reply in Gmail" link and the new Reply control. The job's own
detail page (`/jobs/34`) has no mailbox section at all — its sections are Original job text, Notes,
Follow-ups.

So for any job **without a pending suggestion**, the owner can see that mail exists and who sent it,
and cannot read a single word of it inside the app. Message bodies render only in the
pending-conversation components (`MailboxConversationMessage` bubbles, reached through the Email
decisions panel), which a settled job never shows.

This matters more now than it did yesterday: TASK-152 just recovered readable text for **126
messages** whose bodies were stored empty (137 empty before, 11 after — the remainder are
attachment-only rows). uid 913 on job 34 now holds 2,653 characters of real text that the app still
will not display. The recovery is only worth what the reader can see.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A message in a job's email-history popup can be opened to read its full stored body text, without leaving the app and without the job needing a pending suggestion
- [ ] #2 Rows stay collapsed by default so a 30-message history is still scannable — opening one is an explicit act, and the control says which state it is in (`aria-expanded`)
- [ ] #3 The body renders as plain text exactly as the conversation bubbles do: entities decoded, a literal tag stays literal, no `dangerouslySetInnerHTML` — the TASK-134 #3 guarantee holds in this surface too
- [ ] #4 TASK-138 AC7 is preserved: with a long body open, the popup's `scrollWidth` still equals its `clientWidth` (measured, at the 384px popup width)
- [ ] #5 Verified in the browser on the real case: uid 913 on job 34 shows its recovered text ("We have received your application for the following job position/s ...") where it previously showed nothing
- [ ] #6 `npx tsc --noEmit`, `npm test` and `npm run build` clean; no new dependency
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
The pieces already exist and should be reused, not re-created: `MailboxConversationMessage` already
implements collapse/expand with `aria-controls`/`aria-expanded` and an id of the form
`mailbox-msg-body-{id}`, and it already renders `decodeHtmlEntities(...)` into plain React children.
The flat list is a different, denser component by design (TASK-134 AC8 deliberately kept the popup a
flat per-job list rather than a threaded view), so the goal is to add a disclosure to the existing
row rather than to swap the row for a chat bubble.

Watch the width trap: every row is a grid item, so a long unbroken token in a newly visible body is
exactly the thing that re-breaks TASK-138 AC7. `min-w-0` plus the same `break-words`/
`whitespace-pre-wrap` treatment the bubbles use is the known-good combination — and AC4 asks for it
to be measured, not assumed.
<!-- SECTION:NOTES:END -->
