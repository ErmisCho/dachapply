---
id: TASK-122
title: Edit a reply by talking to a model chosen in the app
status: In Progress
assignee:
  - '@claude'
labels:
  - backend
  - frontend
  - mailbox
  - llm
dependencies:
  - TASK-110
  - TASK-117
priority: high
ordinal: 122000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner request 2026-08-18: *"I should be able to talk with AI (codex, claude, local llm — be able to
choose in the application from what is available) on the spot and change and edit the email to be
sent in the end."*

Owner decision, same day: a real back-and-forth, not a single rewrite box. "kürzer, und Dienstag
statt Montag" → the draft changes → "perfekt" → save.

Two separate things are missing, and they are missing in different ways.

### 1. The draft cannot be edited at all, by anyone

`MailboxDraft` is documented append-only and no view exposes PATCH or DELETE. The only way a draft
changes today is that `check_mailbox` writes a new one. Even a plain textarea would be new capability.

### 2. Model choice is per-machine and invisible — but the machinery to fix it already exists

The mailbox drafter reads `LLM_PROVIDER` from the environment at call time
(`interview_coach._load_llm_config`, `mailbox.py:1198`), supporting `heuristic`, `ollama`,
`ollama-windows` and `openai-compatible`. Nothing in the app selects it, `UserProfile` has no field
for it, and none of the `LLM_*` vars appear in any `.env.example`, in `settings.py`, or in the docs.

Meanwhile **CV generation already solved exactly this problem**. `cv_generator._discover_model_options`
(`cv_generator.py:201`) probes the machine at runtime for four providers — `openai` (from
`~/.codex/models_cache.json`), `anthropic` (only when the `claude` CLI is on PATH; `sonnet`/`opus`/
`haiku`), `ollama` (shells `ollama list`), `lmstudio` (shells `lms ls --llm --json`) — caches for 60s,
and `validate_model_capability` (`cv_generator.py:653`) rejects a request naming something the
machine cannot actually run. The frontend already renders that list as a picker.

So "choose from what is available" is a real capability probe that exists and is proven, pointed at a
different feature. This task reuses it rather than inventing a second one.

Note also that the `claude` and `codex` integrations are **CLI subprocesses**, not HTTP APIs
(`cv_generator.py:761-781`): `claude --print --model X --output-format json --json-schema …` with the
prompt on stdin is already a single stateless structured turn. There is no `anthropic` SDK and no
`ANTHROPIC_API_KEY` anywhere in this repo, and this task does not add one.

### What "conversation" means against a stateless CLI

`--no-session-persistence` means every `claude` invocation is stateless, and the `ollama` path is a
one-shot `POST /api/generate`. Multi-turn therefore means **the app owns the transcript and re-feeds
it**, not that the provider remembers. That is a design constraint to build to, not a detail.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The owner can edit a draft's text directly and save it, with no model involved. This is the floor: if every provider is unavailable the feature must still let someone fix a sentence by hand
- [x] #2 The owner can hold a multi-turn conversation about a draft — each turn sees the earlier turns AND the current draft text, and produces a revised draft the owner can see before accepting. Verified with a second turn that only makes sense if the first was remembered ("shorter" then "actually keep the date I just added")
- [x] #3 The model is chosen in the app from what the machine can actually run, reusing `cv_generator`'s existing discovery and `validate_model_capability` rather than a second probe. A provider that is not installed is not offered, verified by checking the response on a machine where one of them is genuinely absent
- [x] #4 The choice persists per user rather than resetting on every mount — CV generation's picker is React state only, which is a known annoyance and must not be copied
- [ ] #5 Accepting a revision updates the draft in Gmail Drafts, not only in the database — the two must not silently diverge, and the row records that a human edited it rather than leaving `evaluator` claiming a template wrote the text
- [x] #6 The app still never sends mail: `grep -rn "messages.send\|smtplib" backend/` finds nothing new, and the guardrails that already gate a draft (`check_guardrails` — salary floor, do-not-disclose) are re-run on model-revised text before it is written to Gmail. A model must not be able to talk the app past a rule the template could not
- [x] #7 Every provider failure — binary missing, timeout, malformed JSON, non-zero exit — leaves the existing draft intact and says what happened, rather than saving an empty or half-written reply. Verified per provider branch by test, with no test invoking a real model
- [x] #8 A model call cannot hang the request forever: a timeout is passed explicitly (the CV path's `_run_command` takes one and today's model call does not), and the UI shows the turn is in flight
- [x] #9 The `LLM_*` environment variables that govern this are documented in `.env.local.example` — five undocumented vars is how the current situation arose
- [ ] #10 Backend tests cover the transcript being re-fed, the guardrail re-run, provider selection and validation, and every failure branch; `npx tsc --noEmit` and `npm test` clean
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Build AC1 first and separately. It is the fallback the whole feature rests on, it is worth shipping
alone, and it forces the "draft is editable" question (a PATCH route on an append-only model) to be
answered before any model is involved.

The provider dispatch is currently copy-pasted four times (`interview_coach.py:193` and `:495`,
`mailbox.py:584` and `:1059`) — same if/elif on `config.provider`, differing only in temperature,
system prompt and the extracted JSON key. A fifth copy is the wrong move; extracting one caller that
takes (prompt, schema-ish key) is the right one, but that is a refactor touching two modules and
should be its own commit rather than smuggled into this feature.

AC6 is the one most likely to be waved through. TASK-114's lesson was that a textually perfect reply
aimed at the wrong recipient passes every text check; the mirror risk here is a model persuaded to
name a salary below the floor. `check_guardrails` already exists and already blocks — it just has to
run on the revised text too, on the same one entry point.

AC5's "not only in the database": Gmail has no update-draft-in-place through the current code path.
`users.drafts.update` exists; the alternative is delete-then-create, which is worse because
`drafts.delete` is permanent with no Trash. Either way this needs the stored draft id from TASK-121,
so sequence that first or accept that the Gmail side cannot be closed.
<!-- SECTION:NOTES:END -->

## Progress (2026-08-18) — AC1 only, the editable-draft slice

Owner chose delivery in two slices: editable draft first, model conversation second. This is the
first slice; **ACs 2-10 are deliberately not built yet**.

`update_draft_text(draft, new_text, user=None)` in `mailbox.py`, reached by
`POST /api/mailbox-drafts/{id}/edit/` (a single narrow action on a `GenericViewSet` — no generic
PATCH/DELETE, so `MailboxDraft` stays append-only apart from this one path). Scoped so a user can
only edit a draft on a job they can already see.

Order of operations is the load-bearing part and was read rather than assumed: guardrails on the
EDITED text → transport check → Gmail `users.drafts.update` → **then** the database write. If Gmail
throws, the row is untouched, so the two cannot silently diverge. It refuses outright when there is
no stored `gmail_draft_id` rather than updating only locally, and sets `evaluator='human'` so nothing
downstream keeps reporting a template as the author of text the owner rewrote.

### One defect found by measuring, and fixed

The first browser attempt returned **HTTP 500 with a traceback**: `_gmail_api_request` raises
`RuntimeError` on any non-2xx, and that escaped the service. In production that is not exotic — the
owner deletes the draft in Gmail, the refresh token expires, the network drops — and the owner would
see only "error. Please try again." Now caught and returned as a refusal reason, which is what AC7
will require of every provider failure:

    before:  POST /api/mailbox-drafts/1/edit/  ->  500  (Django traceback)
    after:   POST /api/mailbox-drafts/1/edit/  ->  400  {"detail":"Gmail would not accept the edit:
             ... failed with HTTP 404: Requested entity was not found"}

The stored draft was verified unchanged in both cases. Covered by
`test_update_draft_text_returns_a_reason_when_gmail_rejects_the_update`.

Remaining for the second slice: the multi-turn conversation (AC2), in-app model choice reusing
`cv_generator`'s existing discovery and `validate_model_capability` (AC3), per-user persistence of
that choice (AC4), the guardrail re-run on model-revised text (AC6 — the mechanism now exists, it
just needs the model path to route through it), explicit timeouts (AC8), and documenting the `LLM_*`
vars (AC9).

## Progress (2026-08-18) — second slice

`draft_chat.run_chat_turn` holds the conversation; `MailboxDraft.chat_history` persists the
transcript; the chosen `(provider, model)` persists on `UserProfile`, because CV generation's picker
is React state only and resets on every mount, which AC4 explicitly forbids copying.

The providers are stateless — `claude --print --no-session-persistence` and Ollama's one-shot
generate remember nothing — so the app re-feeds the whole transcript every turn. The test that proves
it is a real two-turn exchange: *"shorter"*, then *"actually keep the date I just added"*, asserting
the second call's stdin still contains the first turn's date.

`available_model_options()` is CV generation's existing machine probe, reused rather than duplicated
(AC3). `check_guardrails` re-runs on model-revised text before it can be accepted (AC6). Every
provider failure returns a reason string instead of raising (AC7), matching `update_draft_text`'s
contract — the shape that stopped an unguarded RuntimeError becoming a production traceback earlier
the same day. Timeouts are explicit (AC8) and the `LLM_*` vars are finally documented (AC9).

### Not verified

**AC5's Gmail write-through** and **AC2's conversation in a browser** were not driven end to end
here: the chat UI needs a draft with a live Gmail draft id, and the throwaway database's drafts point
at ids that do not exist in any real mailbox. The accept path reuses `update_draft_text`, which WAS
verified earlier today (guardrails → Gmail → database, refusing with a 400 and leaving the row
untouched when Gmail rejects). Left unchecked rather than claimed.
