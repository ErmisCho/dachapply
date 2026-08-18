---
id: TASK-128
title: Editing a draft hides the way to chat about it
status: In Progress
assignee:
  - '@claude'
labels:
  - frontend
  - mailbox
  - bug
dependencies:
  - TASK-122
priority: medium
ordinal: 128000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner report 2026-08-18: *"I should be able to talk with ai about changing the draft"* — sent while
looking at a draft card that was in edit mode.

The capability exists. `MailboxSuggestionCard` renders both controls, but inside a `{!draftEditing&&…}`
guard:

    {!draftEditing && <span>
       <button …>Edit</button>
       <button … aria-expanded={chatOpen}>Chat to revise</button>
    </span>}

So pressing **Edit** removes the **Chat to revise** button from the page. The owner, having opened the
draft to change it — which is exactly the moment they want help changing it — can no longer see that
chatting is possible. They reported the feature as missing, which is the correct conclusion from what
was on screen.

This is a discoverability failure, not a missing feature, and those are worth separating: the fix is
small and the cost of not making it is that a built feature reads as absent.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The route to the chat is reachable while the draft is being edited — verified in a browser by clicking Edit and confirming the control is still present and works, which is the exact sequence that produced the report
- [ ] #2 Editing by hand and revising by chat compose rather than conflict: a revision accepted from the chat lands in the editor's text, and text typed by hand is what the next chat turn revises. Whichever way the text last changed is the text that gets saved — no path silently discards the other's work
- [ ] #3 It is unambiguous at all times which text will be saved to Gmail if Save is pressed, when both an edit box and a chat revision are on screen
- [x] #4 The chat affordance is discoverable before the owner enters edit mode too — a draft card at rest should make clear that revising by conversation is possible, not only after a click
- [ ] #5 Cancelling an edit does not silently discard a chat revision the owner has already accepted, or if it does, it says so first
- [x] #6 `npx tsc --noEmit` and `npm test` clean
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
The one-line reading is to move the two buttons outside the `!draftEditing` guard. That satisfies AC1
and is probably right, but AC2/AC3 are the reason this is a task rather than a typo fix: once both
surfaces are visible at once there are two sources of truth for the draft text — `draftText` in the
editor and `latestChatRevision` from the conversation — and the existing code already has a
`setDraftText(latestChatRevision||displayedDraftText)` line that picks between them on entering edit
mode. Getting that wrong loses the owner's typing, which is worse than the current bug.

Do not solve it by making chat unavailable during edit and calling that intentional. The owner's
report is the evidence that the two belong together.
<!-- SECTION:NOTES:END -->

## Progress (2026-08-18)

The Edit and "Chat to revise" buttons moved out of the `{!draftEditing&&...}` guard that hid the chat
the moment the owner opened the draft to change it.

MEASURED: clicking **Edit** now leaves *"Chat to revise"* on screen beside Cancel and Save draft —
the exact sequence that produced the report. AC4 holds too: the chat button is present at rest.

There is now one save action, and it always sends `draftText`, so which text reaches Gmail is
unambiguous; "Use this revision" loads a chat revision into the editor rather than saving it
directly.

### Not verified, and one caution

**AC2/AC3/AC5** are implemented but not browser-verified. AC5's discard guard uses native
`window.confirm`, and a native dialog blocks this automation entirely — the renderer froze during
this pass and the tab had to be closed. That is a limitation of the verification tooling rather than
evidence of a defect, but it means the discard-guard paths were read, not driven, and it is worth
knowing that `window.confirm` now sits on a path any automated test would hit.
