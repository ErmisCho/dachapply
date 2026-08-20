---
id: TASK-159
title: Composing a reply on a credential-less backend returns 500
status: Done
assignee: []
labels:
  - backend
  - mailbox
  - bug
dependencies:
  - TASK-133
priority: high
ordinal: 159000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found 2026-08-20 by using the feature on the deployed site: `POST /api/mailbox-messages/698/reply/`
returned **HTTP 500**. The compose UI shipped in PR #52 and is reachable there, so an owner pressing
Reply on the deployed site crashes the request instead of being told why it cannot work.

The endpoint's own docstring promises the opposite: "compose_reply_draft ... returns '' on success or
a short refusal reason otherwise -- **never raises** -- so a Gmail rejection or a guardrail block is a
4xx with the reason and nothing half-written (AC8)".

Mechanism, established by reading rather than guessed:

- `_default_transport()` returns **None** when neither credential pair is configured — it does not
  raise (its own docstring: "TASK-124 AC2: returns None when NEITHER pair is configured"). The
  deployed container has no mail credentials by design; that is the entire reason the run control
  queues a request instead of running a check.
- In `compose_reply_draft()`, `transport = _default_transport()` is followed by a guard that only
  fires when UPDATING an existing draft: `if updating_in_gmail and not isinstance(transport,
  GmailApiTransport)`. Creating a new draft — the compose path — has no such guard.
- `transport.append_draft(...)` on `None` raises `AttributeError`, and the surrounding
  `except (RuntimeError, URLError, OSError)` does not catch it. It escapes to the 500.

`update_draft_text()` is NOT affected and shows the shape the fix should take: its guard is
`if not isinstance(transport, GmailApiTransport): return 'draft editing needs the Gmail API...'`,
which `None` fails cleanly, returning a reason.

Worth recording why the tests missed it: TASK-133 AC8 is covered by a fake transport that REJECTS a
draft, which is a different branch entirely from having no transport at all. The credential-less
backend is exactly the environment the tests never construct, and exactly the one the deployed site
is.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 `compose_reply_draft()` returns a short refusal reason instead of raising when there is no transport, matching the wording style `update_draft_text` already uses for the same situation
- [x] #2 The endpoint answers 4xx with that reason and writes nothing — the contract its docstring already claims (TASK-133 AC8)
- [x] #3 The UI shows the reason rather than a generic failure, so an owner on the deployed site learns that this backend cannot write drafts and that the run happens on their own machine
- [x] #4 Tested with NO transport configured — the environment the existing AC8 test never builds, since a rejecting fake transport is a different branch
- [x] #5 Every other caller of `_default_transport()` is checked for the same unguarded-None shape, and each is either already safe or fixed; the audit is written down so this is not repaired one call site at a time
- [x] #6 Verified on the deployed site: pressing Reply returns a 4xx with a readable reason, not a 500
- [x] #7 Backend suite green
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-08-20 close-out. Fixed in PR #64 (merge 5863ee5), deployed, and verified on the DEPLOYED site with the same request that produced the 500: it now answers HTTP 400 with "this backend has no mail credentials, so it cannot write a draft -- the mailbox check runs on the owner's own machine". AC5's audit of every _default_transport() call site: ingest_threads, backfill_thread_ids, backfill_message_bodies and backfill_historical_mail all guard with isinstance(GmailApiTransport); run_check reaches its own explicit credentials gate first; update_draft_text's isinstance guard already rejects None cleanly. compose_reply_draft's create path was the only unguarded one. AC3 is satisfied by the same response - the UI renders the endpoint's detail string, which now carries the reason. Suite 813 passed.

`has_mailbox_credentials()` already exists and answers exactly this question — the frontend uses it
to choose the run control's wording. Reuse that idea rather than inventing a second capability check.

Do not "fix" this by widening the `except` to catch `AttributeError`: that would swallow real coding
errors inside the transport and turn them into polite refusals, which is worse than the crash.
<!-- SECTION:NOTES:END -->
