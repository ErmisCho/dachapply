---
id: TASK-156
title: An in-app draft edit can strand the stored Gmail draft id
status: Done
assignee: []
labels:
  - backend
  - mailbox
  - bug
dependencies:
  - TASK-121
  - TASK-122
priority: medium
ordinal: 156000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found 2026-08-20 while closing TASK-130 AC3 against the real mailbox.

`update_draft_text()` (services/mailbox.py) calls `transport.update_draft(draft.gmail_draft_id, ...)`
and then **discards Gmail's response entirely** — it persists only `body_text` and `evaluator`
(`draft.save(update_fields=['body_text', 'evaluator'])`). Gmail's `users.drafts.update` returns the
draft resource; nothing re-reads its `id`, so if that id ever differs from the one sent, the stored
`MailboxDraft.gmail_draft_id` silently stops pointing at anything.

Observed state after an in-app edit of draft row 116 (the zooplus reply, edited through
`/api/mailbox-drafts/116/edit/` during TASK-122 verification):

    row 115  r8366615584492002470  never edited in-app  -> found by id and deleted by purge_app_drafts
    row 117  r-6967159284704388853 never edited in-app  -> found by id and deleted by purge_app_drafts
    row 116  r1827526902737800498  edited in-app        -> id no longer resolves in Gmail

The exact mechanism that removed row 116's draft is NOT established and should not be guessed at in
the fix — what IS established, by reading the code, is that this path cannot notice an id change even
if one happens, and that the one row whose id went stale is the one that took this path.

Why it matters: `gmail_draft_id` is what TASK-121 introduced so the app stops guessing, and it is now
load-bearing in two places — a later edit refuses outright without it, and `purge_app_drafts` prefers
it over body matching (TASK-131's whole subject). A stale id degrades both to their fallbacks
without ever saying so.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 `update_draft_text` reads the id back out of Gmail's `drafts.update` response and persists it when it differs from the stored one, in the same save as the body
- [x] #2 A response carrying no usable id leaves the stored id untouched rather than blanking it — asserted by test, since a blanked id is strictly worse than a stale one (it disables editing outright)
- [x] #3 A test drives the id-changed case with a fake transport and asserts the row now points at the new id and a subsequent edit targets it
- [x] #4 The same question is answered for `append_draft`/`compose_reply_draft`: state whether their stored id can go stale the same way, and cover it if so
- [x] #5 Checked against the real mailbox: after an in-app edit, the stored id still resolves in Gmail (list the drafts and match by id), recorded here
- [x] #6 Backend suite green; no test contacts a real mailbox
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-08-20. Shipped in PR #62 (merge d408ec7), deployed, migration 0047 confirmed applied in production. update_draft_text now persists a differing id in the same save as the body and leaves it untouched when the response carries none. AC4 answered: append_draft's callers only ever create new rows so they cannot strand an id, and compose_reply_draft's update branch already guarded against blanking - now pinned by a regression test.

AC5, verified end to end against the real mailbox with the owner's explicit approval to write and then delete one draft: compose_reply_draft wrote draft row 119 (Gmail id r7183633480258912190) onto message 698's thread; update_draft_text then edited it in-app - the exact path that stranded row 116's id before this fix - and the stored id STILL RESOLVES in Gmail afterwards (matched against a live drafts listing). The id happened not to change on this edit, which is the normal case; the point is that the code now notices when it does instead of saving around it. The verification draft was removed with purge_app_drafts --yes immediately after, so the owner's Drafts folder is exactly as it was.

The fix is small — `resp = transport.update_draft(...)`, then take `resp.get('id')` and include
`gmail_draft_id` in `update_fields` when it is truthy and different. The care is in AC2: Gmail
returning an unexpected shape must not be allowed to erase a working id.

Do not "fix" this by re-matching on body text when the id fails — that is exactly the fallback
TASK-131 had to repair, and it is the weaker of the two paths by design.
<!-- SECTION:NOTES:END -->
