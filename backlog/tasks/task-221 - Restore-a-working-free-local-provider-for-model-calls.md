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
- [x] #1 The cause of the model-list decode failure is identified as a version mismatch or a config error, named explicitly, rather than worked around blindly
- [x] #2 At least one free local provider completes a real structured-output call end to end from inside the app, evidenced by the actual response
- [x] #3 The model picker does not offer a local model that cannot satisfy the call, or explains why one is unusable rather than failing at the end of a long wait
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

### AC2 — DONE. Measured in the running app, 2026-09-09

Board at `localhost:8000` (bundle `index-CSa-U3oB.js`, matching `frontend/dist/index.html`), one job
selected, Evaluate with model, provider `lmstudio`, model `deepseek-r1-distill-qwen-7b`, effort
`default`, speed `normal`, Preview evaluation:

> Magenta Telekom — AI Platform Developer f/m/d · **fit 90 · priority high · recommendation apply**
> · "Replaces current fit 94"

**24 seconds**, correctly presented as a dry run with nothing saved. That is a real structured-output
call completing end to end from inside the app. Nothing was committed.

The same run surfaced a defect that is **not** this task's: one selected job produced **two identical
preview rows** and a "Save 2 evaluations" button. `evaluate_jobs` never requires the model's job_ids
to be distinct. Filed as **TASK-223**; nothing was saved.

### AC3 — the tool-use half is now closed, one class remains

`lms ls --llm --json` reports **`trainedForToolUse: false` for all four installed models**, including
the one that evaluates correctly. That is the discriminator between the two paths, so the guard is
built on it rather than on a blocklist:

- lmstudio options now carry `tools` from `trainedForToolUse`.
- `validate_model_capability(..., needs_tools=True)` — the one gate all four call sites already route
  through — refuses a model that cannot read files, for CV generation and readjustment only.
- Absent metadata means capable, so anthropic, openai and every existing caller are untouched.

Measured before and after, same job, same model, in the app:

| | before | after |
|---|---|---|
| CV generation with `deepseek-r1-distill-qwen-7b` | **41s**, three failed attempts, detail was the echoed prompt | **1.0s**, names the cause and what to pick instead |

Left unchecked deliberately. `laser-dolphin-mixtral-2x7b-dpo` cannot load at all (LM Studio:
`llama-server ... exited before becoming healthy, exitCode=1`) and `google/gemma-3-12b` rejects
codex's message sequence in its Jinja chat template — and **`laser-dolphin` is what the picker selects
by default the moment lmstudio is chosen**. Neither is knowable without attempting a load, so the
"does not offer" half cannot be satisfied for them by any probe cheap enough to run at picker time.
Both now fail in ~7s with the provider's own error rather than after a long wait; making that error
legible is TASK-222.

**Owner's ruling, 2026-09-09: the "explains why" half closes this AC.** The gate covers every failure
knowable in advance; a model that simply will not load cannot be predicted without loading it, and
fails fast with the provider's own words. AC3 checked on that basis. Incidentally the "default is the
broken one" complaint went away too: `qwen2.5-7b-instruct` now sorts first in the lmstudio list.

### AC4 — evaluation works, CV generation does not. Left unchecked

Verified separately, as the AC demands, and they disagree:

- **Job evaluation through lmstudio: works.** Evidence above.
- **CV generation through lmstudio: does not.** Run for real in the app before the guard existed:
  *"The selected model could not complete the request. Two automatic repair attempts also failed."*

The cause is measured, not inferred. A minimal probe — one `.tex` file in the working directory, the
same codex flags the app builds, asked only for a marker string and a line count — got this back:

> "Since I don't have access to `probe.tex`, but based on your request, here's how you can obtain the
> information: `tac probe.tex | grep ...`"

The model never called the file-reading tool, ignored `--output-schema`, and **codex still exited 0
and wrote the result file**, so the runner's `returncode or not result_path.is_file()` check waves it
through and only `parse_json_object` catches it.

**Blocker, and it is not a code defect:** no local model on this machine is trained for tool use, so
no code change can close AC4. It needs a tool-capable GGUF loaded in LM Studio — a Qwen2.5-Instruct
or Llama-3.1-Instruct build, something reporting `trainedForToolUse: true` in `lms ls --llm --json`.
The guard added for AC3 is written so the CV path opens by itself the moment one is installed; the
test `test_a_tool_capable_local_model_is_accepted_for_cv_generation` pins that.

#### Pursued that blocker, and it moved to a harder one — measured, 2026-09-09

`lmstudio-community/Qwen2.5-7B-Instruct-GGUF` was downloaded and it reports
**`trainedForToolUse: true`**, the first installed model that does. Three things follow, each
measured rather than argued:

1. **The guard behaves as designed.** The model is accepted for CV generation and reaches the
   provider, so `test_a_tool_capable_local_model_is_accepted_for_cv_generation` is not a fiction.
   It also sorts first in the picker, so the LM Studio default is no longer the unloadable
   `laser-dolphin`.
2. **Tool use genuinely works.** The same file-read probe deepseek failed now returns the real
   marker — `ZEBRA-8817-QUILL` — and quotes the file's contents back. So codex's file-reading tool
   over lmstudio is not the obstacle it looked like.
3. **The obstacle is context length, and it is a hard ceiling.** LM Studio JIT-loads a model at
   **8192** tokens, and **codex's own system prompt is 9,448 tokens**, so every local model has to be
   loaded explicitly first: `lms load <model> --context-length 32768`. That fixed the probe. It did
   not fix generation, because the **CV prompt is 40,654 tokens** and Qwen2.5-7B's architectural
   maximum is 32,768:

       Engine protocol predict request returned 400: request (40654 tokens) exceeds the
       available context size (32768 tokens)

**So AC4 needs a local model meeting BOTH conditions: `trainedForToolUse: true` AND
`maxContextLength` comfortably above ~48k.** Of what is installed, the only long-context models
(`deepseek-r1-distill-qwen-7b` and `google/gemma-3-12b`, both 131072) report no tool use, and the
only tool-capable one caps at 32768. A Llama-3.1-8B-Instruct build (128k, tool-trained) is the
obvious candidate and is **not yet tried**.

Worth the owner's attention independently of this task: **the CV request costs 40,654 tokens on every
provider**, cloud ones included. That is a billing fact, not just a local-model one. Filed as
TASK-224.

*Corrected here rather than left standing:* this first said "most of it is the candidate-evidence
context". That was an assumption and measuring contradicted it —
`_compact_candidate_evidence` already removes **68%**, taking the evidence from 26,458 tokens to
**8,434**, about a fifth of the request. Where the other ~23k goes is not yet measured and is
TASK-224's first criterion.

### Suite

**1084 passed**, full run. Two tests had been broken by this branch and were never caught, because
the earlier pass ran only the 8 new tests plus a previously-green count:

- `test_cv_model_discovery_includes_anthropic_and_installed_local_models`
- `test_optional_model_discovery_cannot_hold_the_popup_beyond_four_seconds`

Both asserted ollama is offered, which the new gate withholds. Both now stub the probe. That also
fixed a hermeticity leak: unstubbed, `_codex_can_enumerate_ollama` made a **live call to
`localhost:11434` from the test suite**, machine-dependent and up to 2s each time. An autouse fixture
in `conftest.py` now defaults it off for every test. The suite got **120 seconds faster** (521s ->
401s), which is the measure of how often it was firing.

The four-second popup ceiling still holds: a probe that times out returns False, which skips
`ollama list` entirely, so the worst case is probe + lms rather than probe + ollama + lms.

### Still to do

**Owner's ruling, 2026-09-09: stop here — AC4 stays blocked and unchecked.** Llama-3.1-8B-Instruct
was not pursued. The task therefore stays **In Progress** rather than being marked Done on three of
four criteria, per TW-005.

What closing AC4 would take, if it is ever picked up:

- A local model that is **both** `trainedForToolUse: true` **and** `maxContextLength` above ~48k;
  Llama-3.1-8B-Instruct (128k, tool-trained) is the obvious candidate.
- Load it explicitly — `lms load <model> --context-length 65536`. The JIT default of 8192 does not
  even fit codex's own 9,448-token system prompt.
- Expect slow rather than instant: 40k tokens of prompt processing on a 7-8B local model is minutes,
  so "works" and "usable" may be different answers.

Open questions this task surfaced but does not own:

- **The CV request is 40,654 tokens**, paid on every provider including cloud. Filed as TASK-224.
- TASK-222 (echoed prompt hides the real error) and TASK-223 (duplicate evaluations) both came out of
  this task's verification.
<!-- SECTION:NOTES:END -->
