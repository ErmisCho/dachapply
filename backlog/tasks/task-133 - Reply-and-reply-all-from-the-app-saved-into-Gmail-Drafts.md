---
id: TASK-133
title: Reply and reply-all from the app, saved into Gmail Drafts
status: In Progress
assignee: []
labels:
  - backend
  - frontend
  - mailbox
priority: high
ordinal: 133000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner request 2026-08-19: *"with the option to reply, reply all and or select recipients."*

Today the app writes ONE kind of reply: a generated draft to the sender of one matched message,
threaded onto it. The owner cannot choose to reply-all, cannot add or remove a recipient, and cannot
start a reply to an earlier message in the thread.

### The guarantee this must not break, and the decision that shapes it

**This app never sends mail.** That is not incidental — it is asserted in the module docstring, in
TASK-110, re-verified by `grep -rn "messages.send\|smtplib" backend/` in TASK-114, TASK-121 and
TASK-122, and it is why TASK-114's incident (112 polite replies drafted at newsletters, two aimed at
marketing addresses) cost nothing but a cleanup. With sending, that same bug mails strangers.

Owner decision 2026-08-19, asked explicitly: **compose in the app, save into Gmail Drafts, press Send
in Gmail.** So this task adds recipient control and reply-all, and adds no send path. `gmail.send`
scope is not requested and `users.messages.send` still appears nowhere.

That also keeps the useful property that a mistake is recoverable: a wrong draft is deleted, a wrong
send is not.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The owner can compose a reply to any message in a conversation, not only the one that produced a suggestion
- [x] #2 Reply and reply-all are distinct and correct: reply goes to the sender, reply-all preserves the other recipients, and which one is selected is visible before saving — derived from the message's own headers, not guessed
- [x] #3 Recipients are editable before saving: the owner can add or remove a To or Cc, and what will be saved is shown verbatim rather than described
- [ ] #4 The result is written to Gmail Drafts on the correct thread, verified by the draft appearing in that Gmail conversation rather than as a detached message
- [x] #5 The app still never sends: `grep -rn "messages.send\|smtplib" backend/` finds nothing new, no `gmail.send` scope is requested, and a test asserts the send endpoint is never called
- [x] #6 `check_guardrails` runs on the composed text before it is written, exactly as it does for a generated draft — a hand-composed reply must not get past the salary floor or do-not-disclose rules that a template cannot
- [x] #7 A recipient the owner did not intend cannot be introduced silently: reply-all on a message with a `Reply-To` or a mailing-list header behaves predictably and the final recipient list is what was shown
- [x] #8 Failure is legible: a Gmail rejection returns a reason and leaves nothing half-written, matching `update_draft_text`'s existing contract rather than raising into a 500
- [x] #9 Backend tests cover reply vs reply-all recipient derivation, recipient editing, the guardrail run, and the no-send assertion; `npx tsc --noEmit` and `npm test` clean
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-08-20 close-out (evidence: backend suite 783 green; browser measurements on the built bundle at localhost:8000; prod-DB reads and app-command runs with the owner's approval; merges #51/#52/#53 live with HTTP 200): Compose UI shipped in #52 and driven live: Reply control on every message opens a dialog labelled with the real message; mode radios visible; derived To prefilled; Cc edited to a new address and the POST carried exactly the shown lists verbatim; 200 -> 'Saved to Gmail Drafts - Nothing was sent'. AC4 stays unchecked for one glance: open Gmail and confirm the new draft sits inside the ISG conversation (threadId is test-asserted; only the Gmail-UI placement is unobserved).

`build_reply_mime` already builds a threaded reply (In-Reply-To/References) and `append_draft` writes
it; `update_draft_text` already does the guardrail-then-Gmail-then-database ordering and returns a
reason string instead of raising. This is those three, with a recipient list that comes from the UI
instead of being implied.

AC2's derivation is the fiddly part and belongs in one tested pure function: reply = the message's
`Reply-To` or `From`; reply-all = that plus its `To` and `Cc`, minus the owner's own addresses. The
owner has more than one address (`GMAIL_IMAP_USER`, `CODEX_CV_OWNER_EMAIL` and possibly the
`DEFAULT_FROM_EMAIL` sender), so "minus me" must consult all of them or the owner ends up cc'ing
themselves.

TASK-132 stores the whole thread including sent messages; once that lands, "reply to any message in
the conversation" has something to reply to. Until then this can only target ingested inbox messages.
Note the current `RawMessage` does not carry `To`/`Cc` at all — TASK-114 added only the bulk-marker
headers — so reply-all is not derivable from what is stored today. That is the first thing to fix,
and it is a schema change, not a UI one.
<!-- SECTION:NOTES:END -->
