---
id: TASK-132
title: Make a conversation actually be the whole thread
status: Done
assignee: []
labels:
  - backend
  - mailbox
  - data
  - privacy
dependencies:
  - TASK-117
  - TASK-121
  - TASK-127
priority: high
ordinal: 132000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner report 2026-08-19, comparing the app's zooplus card against their Gmail: *"I have all these
messages that should be visible in a threaded conversation … instead you show me that you received
some emails but you couldn't find the body."*

Two separate gaps, both measured against production the same day.

**1. Almost nothing has a body.**

    messages total: 653 | empty body: 648 | with body: 5

`MailboxMessage.body_text` only arrived with TASK-117, yesterday. Every message ingested before that
had its body read off the wire and deliberately dropped. So the conversation view renders
*"(no body recorded)"* for everything older than a day — which is honest, and useless.

**2. A "conversation" is a handful of inbox fragments, not a thread.**

    messages from a zooplus sender in the app: 3
    threads in the owner's Gmail for zooplus:  4

Missing entirely: *"zooplus would like to get to know you!"* (10 Jun), *"Thank you for applying to
zooplus"* (3 Jun), and — in every thread — **the owner's own replies**, which live in Sent and were
never read. Gmail shows "Julia, me 5" for a thread the app knows two messages of.

`fetch_new` reads new inbox mail and matches it by sender domain. That is the right primitive for
"tell me what arrived", and the wrong one for "show me the conversation". A thread is the unit the
owner thinks in, and the app has never had one.

**Every row has a `gmail_id` (653 of 653)**, and TASK-121 began storing `thread_id`, so both gaps are
recoverable from Gmail rather than lost.

### The privacy consequence, stated up front

This stores the owner's own sent mail, not just what they received. TASK-117 already reversed the
minimal-metadata default for received bodies, knowingly. This widens it again, and the owner asked
for it (decision 2026-08-19: bodies plus whole threads including their replies). Recorded here so the
next reader sees a decision rather than a drift.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A matched message's whole Gmail thread is ingested, not just the inbox message that triggered the match — including messages the owner sent, verified against the zooplus thread Gmail shows as "Julia, me 5" where the app currently has 2
- [x] #2 A message the owner sent is distinguishable from one they received, so the conversation reads as an exchange rather than a flat list — the view must be able to say who spoke without guessing from the address
- [x] #3 The 648 existing rows with no body are backfilled from Gmail by their stored `gmail_id`, and the count actually filled is reported — not assumed from the count attempted
- [x] #4 Backfill is resumable and idempotent: it can be interrupted and re-run without duplicating rows or re-fetching what it already has, because 653 messages is a long enough job to be interrupted
- [x] #5 Thread ingestion cannot explode the table: state the bound (per-thread message cap, date floor, matched-jobs-only) rather than leaving "fetch everything" implicit, and report what was skipped
- [x] #6 The append-only guarantee survives: existing rows are updated only in `body_text` and thread linkage, never rewritten or deleted, and `uid` stays unique
- [x] #7 No test contacts a real mailbox, and the no-send guarantee is unchanged — `grep -rn "messages.send\|smtplib" backend/` finds nothing new
- [x] #8 Run against the owner's real mailbox with before/after counts recorded in this file: 648 empty bodies and 3 zooplus messages are the numbers to beat
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-08-20 close-out (evidence: backend suite 783 green; browser measurements on the built bundle at localhost:8000; prod-DB reads and app-command runs with the owner's approval; merges #51/#52/#53 live with HTTP 200): AC1: ingest_threads --yes (limit raised to cover all 69 threads) created 52 messages; the zooplus thread now holds 10 stored messages, 5 of them the owner's. AC3: under TASK-149's fix the body backfill terminates honestly - 126 attempted / 0 fillable (the remaining rows genuinely return no body). AC8 counts: 940 -> 992 (ingestion) -> 1000 (live run); empty bodies 136 -> 126; sent_by_owner 10 -> 59.

`users.threads.get` returns every message in a thread in one call, which makes AC1 and AC3 the same
mechanism rather than two: fetch the thread, store what is missing, fill the bodies you already have
rows for.

`GmailApiTransport` already does OAuth, paging and raw-message decoding (`fetch_new`, `list_drafts`),
so this is a third read method beside them, not new plumbing. IMAP has no thread concept — refuse
there the way `purge_app_drafts` and `update_draft_text` already refuse, rather than half-implementing.

`MailboxMessage.uid` is globally unique and doubles as the resume marker (`MAX(uid)`), so inserting
historical thread messages must NOT use the same sequence — reusing it would move the marker
backwards or collide. Read `run_check`'s comment on locally-assigned uids before choosing.

AC5 matters: the owner has 653 matched messages across an unknown number of threads, and some threads
are long. Fetching every thread of every message unbounded is how a "quick backfill" becomes an hour
of API calls and a table nobody expected. A per-thread cap plus matched-jobs-only is the obvious
bound; whatever is chosen, say it in the output.

AC2 needs a stored flag rather than comparing the From address at render time — the owner has more
than one address, and a guess that is right today breaks quietly.
<!-- SECTION:NOTES:END -->
