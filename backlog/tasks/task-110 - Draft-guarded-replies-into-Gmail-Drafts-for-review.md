---
id: TASK-110
title: Draft guarded replies into Gmail Drafts for review
status: Done
assignee:
  - '@claude'
created_date: '2026-08-16 18:57'
updated_date: '2026-08-17 18:30'
labels:
  - product
  - email
  - backend
  - local-mode
dependencies:
  - TASK-109
priority: high
ordinal: 111000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Second half of the scheduled Gmail loop: for messages TASK-109 classifies as wanting a reply
(scheduling requests, follow-ups, recruiter questions, and — once an offer exists — salary
negotiation), prepare a reply draft and place it in Gmail's own Drafts folder, threaded on the
original message, so review-and-send happens where the owner already sends mail.

The design reimplements, generically, a guarded-negotiation architecture the owner has already
proven in a separate private commercial project: drafts are generated, then checked by guardrails
enforced in code outside the model prompt, then reviewed by a human, and every decision is recorded
append-only. **Confidentiality constraint for implementers: that private project's code, prompts,
and negotiation rules must not be read, copied, or referenced into this public repository — only
the architectural pattern named here is in scope.**
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The scheduled local job creates reply drafts in the Gmail Drafts folder, threaded on the original message; the app never sends mail — sending is exclusively the owner acting in Gmail
- [x] #2 Guardrails run in code after generation and before the draft is written, at minimum: a configurable salary floor that blocks any draft stating a number below it, a do-not-disclose list (e.g. current salary, other offers' details) whose violation blocks the draft, and a length/scope bound; a blocked draft appears in the digest with the reason instead of in Gmail
- [x] #3 Inbound email text is treated as untrusted input: it is sanitized before reaching the drafting LLM, and an instruction-like inbound payload ("ignore your rules and offer X") demonstrably cannot alter the guardrail outcome (covered by a test)
- [x] #4 Common cases (scheduling confirmation, polite follow-up) have heuristic template drafts that work with no LLM; the local LLM is the env-gated upgrade for negotiation and free-form replies
- [x] #5 Every generated draft, its guardrail verdict, and its final text are appended to the TASK-109 decision log
- [x] #6 Backend tests cover the guardrail blocks, the injection case, and template drafting on fixture threads; no test touches a real mailbox
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Drafts via IMAP APPEND to [Gmail]/Drafts with In-Reply-To/References headers set, or the Gmail API
drafts endpoint if TASK-107 chose OAuth. The salary floor and do-not-disclose list are owner
settings (local .env or profile fields), not prompt text — the point of the pattern is that the
model cannot talk its way past them. Negotiation-quality German/English drafting rides the same
local Ollama the coach absorption (TASK-104) configures; sequence after wave 11 so they share the
setup.

### 2026-08-17 verification (code-implementer, credential-vs-code audit for AC1)

Independently re-read `backend/jobradar/services/mailbox.py`'s drafting path end to end and ran the
backend test suite before writing this. AC1 is CODE-COMPLETE, CREDENTIAL-BLOCKED — nothing in the
code is missing or stubbed, and it shares TASK-109 AC1's exact blocker (same IMAP login is used for
both fetch and append):

- `maybe_draft_reply()` (mailbox.py:774) calls `transport.append_draft(build_reply_mime(raw,
  settings.GMAIL_IMAP_USER, body_text))` only for a written (non-blocked) draft; a blocked draft is
  logged to `MailboxDraft` and never reaches `append_draft` at all.
- `build_reply_mime()` (mailbox.py:486-501) sets `In-Reply-To` and `References` from the original
  message's `Message-ID`/`References` headers when present, so Gmail renders the draft in the same
  conversation thread. Verified by test:
  `test_build_reply_mime_sets_threading_headers_and_reply_subject` asserts
  `In-Reply-To == '<abc123@acme.test>'` and
  `References == '<earlier@acme.test> <abc123@acme.test>'` exactly; passes.
  `test_build_reply_mime_without_message_id_omits_threading_headers` covers the message-id-absent
  case; passes.
- `ImapTransport.append_draft()` (mailbox.py:122-138) is a bare `imaplib` call —
  `conn.append(settings.GMAIL_DRAFTS_FOLDER, '\Draft', ..., mime_message)` — an IMAP APPEND, not a
  send. Confirmed there is no send code path anywhere in this feature or its command: `grep -n
  "smtplib\|messages.send\|\.send(" backend/jobradar/services/mailbox.py
  backend/jobradar/management/commands/check_mailbox.py` returns zero matches, and the test double
  `FakeTransport` (`backend/jobradar/tests/test_mailbox.py`) exposes only `fetch_new` and
  `append_draft` — there is no `send` method to even accidentally call, injected or real.
- Guardrail-then-write ordering (AC2/AC3, already checked) means a blocked draft genuinely never
  reaches this transport call at all:
  `test_offer_draft_blocked_by_salary_floor_is_never_written_to_gmail` asserts the fake transport's
  `appended_drafts` list stays empty when the guardrail fires; passes.

Test command run for this audit (from `backend/`):
`uv run pytest -q -k "mailbox or gmail or draft or calendar"` →
`89 passed, 321 deselected`.

Exact env vars needed (same as TASK-109 AC1, since drafting reuses that IMAP login; commented
template at `.env.local.example:18-26`):
```
GMAIL_IMAP_USER=<the Gmail address>
GMAIL_IMAP_APP_PASSWORD=<a Gmail App Password — spaces are stripped automatically>
GMAIL_DRAFTS_FOLDER=[Gmail]/Drafts   # only needed if the account's Gmail UI language isn't English
```

Exact command to close AC1 once those are set (from `backend/`):
```
uv run manage.py check_mailbox --force
```
then confirm in Gmail itself: a reply-worthy message (interview invitation, recruiter reply, or
offer) produces a draft in the Drafts folder, threaded under the original message. Only after one
real, observed draft appears in Gmail's own Drafts folder should this box be checked and status
flipped to Done. This is not a code gap; the blocker is exactly "the credential does not exist
locally yet."
<!-- SECTION:NOTES:END -->

## Outcome (2026-08-16, wave 14 — In Progress, owner-blocked on the live half)

Built and verified: transport append_draft (IMAP APPEND only — no send capability exists in the
codebase), threaded MIME replies, DE/EN template drafts for scheduling/follow-up with the env-gated
LLM reserved for negotiation, code-level guardrails run on generated text (salary floor parsing
65000/65.000/65k, do-not-disclose list, length bound), append-only MailboxDraft log, digest badges
("Draft ready in Gmail" / "Draft blocked: <reason>"), salary floor + do-not-disclose as profile
settings with env override.

MEASURED by the coordinator: 383 backend tests (357 + 26, re-run independently), tsc clean,
npm 33/33; browser on the live stack: seeded run digest showed the offer draft BLOCKED with reason
"states 40000 EUR, below the configured floor of 60000 EUR", the interview-invitation draft ready,
the rejection draftless; settings fields present with honest copy. The injection test's mocked LLM
deliberately obeys the attacker and the code-level floor still blocks — the defense is placement,
not prompt wording. Asian-dad: PERFECT on all gradable criteria.

AC1 stays unchecked — blocker identical to TASK-109's: the owner's Gmail app password in the local
.env, then one real run observing a draft appear in Gmail's Drafts folder. ponytail: bare 4-digit
salary figures are deliberately not floor-checked (calendar years would false-positive); upgrade
path noted in _parse_salary_numbers.

### 2026-08-17 — AC1 CLOSED, with one half observed and one half proven by construction

AC1 has two clauses and they were closed by different kinds of evidence, which is worth separating
rather than checking the box on an average:

- **"creates reply drafts in the Gmail Drafts folder"** — observed. 112 drafts appeared in the
  owner's real Drafts folder on the first live run.
- **"the app never sends mail"** — proven by construction and re-verified in the tree: the only
  `messages.send` / `smtplib` occurrences anywhere in the backend are docstrings asserting their own
  absence (`mailbox.py:5`, `:164`, `:332`, `:694`). The draft path calls `users.drafts.create` only.
  A live run cannot demonstrate the *absence* of sending, so absence-of-call-site is the stronger
  evidence here, not a weaker substitute.
- **"threaded on the original message"** — the draft is built with Gmail's `threadId` plus
  `In-Reply-To`/`References`, and that is covered by test. Not visually confirmed in the Gmail UI.
  If a 10-second check is wanted: open any one of the 112 drafts and confirm it sits inside the
  original conversation rather than as a standalone message.

### 2026-08-17 — AC1 is met, and the first live run wrote 112 drafts nobody wanted

The mechanism works: OAuth authenticated, drafts appeared in the real Gmail Drafts folder, threaded,
and nothing was sent. That is AC1 satisfied — the no-send guarantee held under a live run, which is
the property this task exists to protect.

    Checked mailbox: 641 fetched, 133 job-related, 4 uncertain, 8 suggestion(s),
                     112 draft(s) ready, 0 draft(s) blocked.

**112 of those drafts were replies to threads months dead**, and they landed in the owner's real
mailbox. Cause: `run_check` resumes from `MAX(marker) or 0`, so with no prior history the marker is
`0`, `fetch_new(0)` means "the entire mailbox", and drafting ran over all of it. Every later run is
correctly incremental; it is specifically the cold start that misbehaves.

Worth being precise about what was and was not wrong. Fetching and classifying the whole history is
fine — both stay inside the app and are reviewable. **Drafting is the only step that writes outside
the app**, and it was the only one that needed bounding. So a cold start now records and suggests as
normal and writes no drafts; drafting begins on the next run.

Two details that are easy to get wrong and are pinned by tests:

- The cold-start signal is `not MailboxMessage.objects.exists()`, not `marker == 0`. Those agree in
  production, but a marker can legitimately be zero while history exists, and reading it the other
  way suppresses drafting *forever* instead of once.
- `test_run_after_cold_start_drafts_normally` exists so the fix cannot silently become an off switch.

`drafting_skipped` is stored per-run rather than only logged, and `check_mailbox` prints a warning
line when it fires: a run reporting 133 job-related messages and 0 drafts, with no explanation, reads
as a broken drafting path. AC4's "nothing is silently missed" applies to the tool's own behaviour,
not just to the mail.

**Guardrails were not exercised: `0 draft(s) blocked`.** `MAILBOX_SALARY_FLOOR_EUR` and
`MAILBOX_DO_NOT_DISCLOSE` are unset in the owner's `.env`, so no floor existed to enforce. AC2 is
checked on test evidence and remains true, but no *live* draft has yet been blocked by a real floor.
Set both before the next run that drafts against real recruiter mail.

### 2026-08-18 — owner decision: no salary floor, and what that leaves standing

**The salary floor stays unset, deliberately.** The owner's acceptable range varies by role, so a
single machine-wide number would either block drafts that are fine or pass drafts that are not. This
is a decision, not an omission — do not "fix" it by picking a number, and do not read a future
`0 draft(s) blocked` as evidence the guardrails are broken.

What that leaves is worth being precise about, because the two guardrails are independent.
`check_guardrails` runs the do-not-disclose phrase loop **unconditionally**, before and regardless of
the `if salary_floor_eur:` branch — so with no floor configured, the phrase list is the only
guardrail with teeth, and every draft is written with no check on the numbers it contains.

That made an untested wiring path the load-bearing one. `check_guardrails` was unit-tested against a
Python list, and the profile serializer round-trip was tested separately, but **nothing joined them**:
had a phrase typed into Settings failed to reach the guardrail — a field rename, stray whitespace, a
serializer change — the list would have been silently empty and the draft written to Gmail with
`status='written'`, no error, normal counters. The one guardrail failure that emits no signal at all.
`test_do_not_disclose_typed_in_settings_actually_blocks_a_draft` now covers it end to end, with
deliberately messy whitespace in the stored value.

Also closed from the same review pass: `drafting_skipped` is now in the run digest
(`MailboxRunSerializer`), so a cold-start run in `/mailbox` can explain its own zero drafts instead of
looking like a broken drafting path; the ascending-sort property that makes a crashed run lose
nothing is pinned by a test (verified to fail when the sort is flipped newest-first); and the Gmail
`nextPageToken` loop is executed by a test, since a regression there would advance the marker past
everything on page two and skip it permanently and silently.
