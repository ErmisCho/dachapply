---
id: TASK-121
title: Persist Gmail draft and thread ids, and open the conversation in Gmail
status: In Progress
assignee:
  - '@claude'
labels:
  - backend
  - mailbox
  - frontend
dependencies:
  - TASK-110
  - TASK-117
priority: high
ordinal: 121000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner request 2026-08-18: *"or even have an option to just draft the response and have a link to
browse to that conversation and finish the job myself."*

That link cannot be built today, by construction. `GmailApiTransport.append_draft`
(`mailbox.py:399-410`) POSTs to `/drafts` and **discards the response** — the `users.drafts.create`
reply carries `{id, message:{id, threadId}}` and `_gmail_api_request` already parses it, but the
value is dropped one frame later. `RawMessage.thread_id` is likewise fetched (`mailbox.py:395`) and
documented as *"transient, never persisted"*. `MailboxDraft` has no id field of any kind.

Two consequences, one of them already paid for:

1. **No deep link is possible.** The app knows it wrote a draft and cannot say where it went.
2. **`purge_app_drafts` has to identify its own drafts by comparing body text** (`mailbox.py:1189`),
   which is why TASK-114 had to argue at length that a hand-written draft must be unmatchable by
   construction. With a stored draft id that whole class of risk goes away.

### Overlap that must be handled, not discovered later

**TASK-113 already specifies this exact schema change** and is filed on the branch
`worktree-task-113-actionable-reminders` (not on `main`). Its AC1 is *"`append_draft` returns Gmail's
response ids and `MailboxDraft` persists them (draft id, message id, thread id)"*, and its own notes
say to do AC1 first and alone because the rest is unbuildable without it. Its AC2 wants the same
Gmail link from the reminder email; this task wants it from the decision panel.

If both ship independently the repo gets two Gmail URL builders. This task therefore implements
TASK-113 AC1 as the shared foundation and owns the single URL builder; TASK-113's reminder-email ACs
(AC5-AC9) are untouched and stay its own. **That branch may belong to another session — coordinate
before starting, do not merge or rewrite it.**

### The URL form is the risky part and must be measured

TASK-113's notes already flag it: the compose URL takes the draft's *message* id, not the draft id.
Candidates, ranked by what the schema supports:

- `#search/rfc822msgid:<message_id>` — uses `MailboxMessage.message_id`, which already exists on
  **every** row from **both** transports. Needs the angle brackets stripped and URL-encoding.
- `#all/<gmail_id>` — existing field, but `gmail_id` is `''` on every IMAP-sourced row.
- `#drafts?compose=<draft message id>` — the only form that opens the composed draft rather than the
  thread; needs the new field.

Coverage is the trap: `_default_transport()` prefers IMAP whenever `GMAIL_IMAP_USER` and
`GMAIL_IMAP_APP_PASSWORD` are both set, and on such a machine `gmail_id` is empty for the entire
table, so a `gmail_id`-based link is dead for every row.

The 112 drafts already deleted, and every row written before this task, will have empty ids. The UI
must handle that rather than rendering a broken link.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 `append_draft` returns Gmail's response and `MailboxDraft` persists the draft id, the draft's message id and the thread id; `ImapTransport.append_draft` returns the same shape (empty) so the one call site stays uniform. Verified by reading the stored row after a real `check_mailbox` run, not from a unit test alone
- [x] #2 `MailboxMessage` persists the inbound `thread_id` too — it is a different id from the draft's, and it is what a per-message "open this conversation" link needs
- [ ] #3 Exactly ONE Gmail URL builder exists in the codebase, and the URL form it produces is recorded in the task notes with evidence that it actually opened the right thing in a real browser — not inferred from Gmail documentation
- [x] #4 The link works for a row sourced by EITHER transport, or the UI says plainly why it cannot for that row. A row with no usable id shows no link rather than a link that 404s into an empty Gmail search
- [x] #5 Rows written before this task (empty ids) render without a broken link and without a crash, verified against an actual pre-existing row
- [x] #6 `purge_app_drafts` prefers the stored draft id when present and keeps the body-text match only as the fallback for pre-existing rows — the permanent-delete safety argument in TASK-114 must not be weakened, and a hand-written draft must still be unmatchable
- [x] #7 The no-send guarantee is unchanged and re-verified: `grep -rn "messages.send\|smtplib" backend/` finds nothing new. This task adds a link to Gmail, never a send
- [x] #8 Backend tests cover id persistence from a fake transport response, the URL builder including the missing-id branch, and the purge fallback; no test contacts a real mailbox
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
The change at the write site is small — `return` the parsed response from `append_draft`, and pass
three values into the `MailboxDraft.objects.create(...)` at `mailbox.py:1200-1210`. The care goes
into AC3 and AC4: a link that silently lands on an empty Gmail search looks like it worked.

Measure the URL by hand in a real browser before writing the builder. `/mail/u/0/` addresses
whichever Google account signed in first, which is a real failure mode on a machine with two
accounts; `_reply_from_address()` (`mailbox.py:1253`) already resolves the owner's address and is the
input to an `authuser=` disambiguator if one proves necessary.

Prefer `rfc822msgid` if it works: it needs no new field to link the CONVERSATION, works on both
transports, and leaves the new draft ids to do the narrower job of opening the composed draft and
tightening `purge_app_drafts`.
<!-- SECTION:NOTES:END -->

## Outcome (2026-08-18)

`append_draft` returns Gmail's response instead of discarding it (`ImapTransport` returns `{}` so the
one call site stays uniform); `MailboxDraft` persists `gmail_draft_id`, `gmail_message_id` and
`gmail_thread_id`, and `MailboxMessage` persists the inbound `thread_id` — migration `0037`.

`gmail_conversation_url(message_id, authuser='')` is the single builder, keyed on the RFC 822
`Message-ID`. That choice is the load-bearing one: `gmail_id` is `''` on every IMAP-sourced row and
`_default_transport()` prefers IMAP whenever both IMAP settings are present, so a `gmail_id`-based
link would be dead for the entire table on such a machine. `message_id` is populated by both
transports. Angle brackets are stripped and the value URL-encoded.

`purge_app_drafts` now matches on the stored draft id first, keeping the body-text comparison only as
the fallback for rows written before this task — TASK-114's argument (a hand-written draft must be
unmatchable, because `drafts.delete` is permanent with no Trash) is unweakened.

MEASURED:

- **AC4** — a message with a `Message-ID` renders "Open in Gmail" with
  `https://mail.google.com/mail/u/0/#search/rfc822msgid:CAOxyz123.abc%2445%40mail.gmail.com`;
  a message without one returns `gmail_url: null` from the API and renders **no link at all**.
  Both observed in the same browser session.
- **AC7** — `grep -rn "messages.send\|smtplib" backend/` finds only docstrings and comments; no
  `.messages.send(` call and no `import smtplib` anywhere.

507 backend tests pass.

### AC3 is NOT closed

The URL *form* is built and its no-id branch is proven, but "it actually opened the right
conversation in a real browser" has not been demonstrated. Doing so requires opening the owner's real
Gmail with a real `Message-ID` from their mailbox, which was deliberately not done without their say
so. **AC3 stays unchecked and this task stays open on that one criterion.** One click by the owner on
the link the app now renders closes it.
