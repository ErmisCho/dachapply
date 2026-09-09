---
id: TASK-221
title: Restore a working free local provider for model calls
status: In Progress
assignee: []
labels:
  - backend
  - llm
  - infrastructure
dependencies: []
priority: high
ordinal: 220000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Filed 2026-09-08 from TASK-220's verification. `codex exec --oss --local-provider ollama` does not
work on the owner's machine, and it is the command `generate_cv_package` builds, so CV generation
through ollama is broken today too. This was found by measurement, not inference: both failures were
reproduced on the command line outside the app.

1. `gemma3:4b does not support tools` — `codex exec` requires a tool-capable model, so several
   installed ollama models cannot be used at all.
2. With the tool-capable `gpt-oss:20b`, codex cannot read ollama's model list:
   `failed to decode models response: missing field 'models'`. Ollama answers with an OpenAI-style
   `data` array that this codex build rejects.

The consequence is that every model path in this project — CV generation, evaluation, drafts,
interview coach — currently reaches only `anthropic` and `openai`, both of which bill. TASK-220's
premise that "Ollama keeps it free" does not hold on this machine right now.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The cause of the model-list decode failure is identified as a version mismatch or a config error, named explicitly, rather than worked around blindly
- [ ] #2 At least one free local provider completes a real structured-output call end to end from inside the app, evidenced by the actual response
- [ ] #3 The model picker does not offer a local model that cannot satisfy the call, or explains why one is unusable rather than failing at the end of a long wait
- [ ] #4 CV generation and job evaluation both work through the restored local provider, verified separately rather than assumed from a shared code path
<!-- AC:END -->

## State of play (handoff, 2026-09-09)
<!-- SECTION:NOTES:BEGIN -->
Branch `task-221-local-provider`. Sealed rubric at `.claude/.asian-dad/task-221-rubric.json` (gitignored,
written before implementation per TW-001).

### AC1 — DONE. Cause identified and named, with evidence

codex-cli **0.146.0** asks ollama for its models over the OpenAI-compatible `/v1/models` route but
decodes the reply with the **native `/api/tags` schema**, which is the one carrying a top-level
`models` key. Ollama **0.32.9** answers `{"object":"list","data":[...]}`. Codex reports
`missing field 'models'` and the run **aborts** — verified fatal for `gpt-oss:20b` and
`qwen3-coder:latest`, both tool-capable, so it is not the tool-capability problem it first looked like.

Both endpoints exist and work; codex is pairing the wrong one with the wrong decoder. Reproduced on
the command line outside the app:
- `curl localhost:11434/v1/models` -> `{"object":"list","data":[...]}`  (what codex reads)
- `curl localhost:11434/api/tags`  -> `{"models":[...]}`                (what codex decodes for)

The separate `gemma3:4b does not support tools` error is a real but **different** constraint, and it
is codex's requirement, not ollama's: `gemma3:4b` answers a structured-output call happily over
ollama's own `/v1/chat/completions` with `response_format: json_schema` — measured, returned
`{"answer": "ok"}`.

### AC2 — a working free local provider EXISTS: lmstudio

`codex exec --oss --local-provider lmstudio --model deepseek-r1-distill-qwen-7b` completes a real
structured-output call and writes its result file. lmstudio does **not** hit the model-list bug at all.
Note `lms server start` is required first; it was not running.

`google/gemma-3-12b` fails on lmstudio for a third, unrelated reason — its Jinja chat template
rejects codex's message sequence (`Conversation roles must alternate user/assistant/...`).

### Done in this branch

- `run_structured_model` now parses with `parse_json_object` instead of a bare `json.loads`.
  deepseek-r1-distill-qwen-7b honours `--output-schema` loosely and wraps its answer in a ```json
  fence; the paste path has always needed exactly this tolerance, so it is reused, not rewritten.
- `_codex_can_enumerate_ollama()` probes the very response codex chokes on, and ollama models are
  withheld from the picker while it fails. It is a live probe, not a hard-coded verdict: the models
  return by themselves once either side ships a build that agrees. Confirmed live — ollama now offers
  0 models, lmstudio offers 4, anthropic/openai unaffected.
- `backend/jobradar/tests/test_local_provider.py`, 8 tests, no provider launched.

### Still to do

- **AC2 end to end from inside the app** — not yet run. The dev server was restarted with this code
  but the browser run was not completed. Select a job, pick lmstudio / deepseek-r1-distill-qwen-7b,
  press Preview, record the returned fit/priority/recommendation and the elapsed time.
- **AC3** — currently satisfied by the "does not offer" half. Unusable ollama models now vanish from
  the picker **silently**; if that is judged confusing, the AC's other half ("explains why one is
  unusable") needs frontend work.
- **AC4** — CV generation through lmstudio is NOT verified and is the real risk in this task. The CV
  prompt opens with "Read the copied LaTeX source files", so that path genuinely depends on codex's
  file-reading tools, which a plain chat completion would not provide. It must be run for real, not
  argued from the code.
- Full backend suite has not been run since these edits; only the 8 new tests plus the previously
  green 1074.
<!-- SECTION:NOTES:END -->
