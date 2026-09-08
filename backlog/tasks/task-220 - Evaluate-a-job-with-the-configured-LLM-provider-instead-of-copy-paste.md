---
id: TASK-220
title: Evaluate a job with the configured LLM provider instead of copy-paste
status: In Progress
assignee: []
created_date: '2026-09-08 11:05'
labels:
  - backend
  - frontend
  - llm
  - evaluation
dependencies: []
priority: high
ordinal: 219000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Every job currently needs: generate prompt in /prompts, open ChatGPT, paste, copy the JSON back, paste into /import. That loop gates score, priority and to_apply, so it gates the whole pipeline. The README justifies it as avoiding paid LLM API calls, but that rationale no longer holds: cv_generator, cv_tasks, draft_chat, interview_coach and mailbox already call openai/anthropic/codex/ollama, and the mailbox does it unattended on a schedule. The provider abstraction, the model picker and the strict JSON importer all already exist; what is missing is the wire between build_prompt and the provider call. Ollama keeps it free. Filed 2026-09-08.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A job can be evaluated from within the app using the same provider and model layer CV generation uses, with no copy-paste step
- [x] #2 The model response is validated by the existing strict JSON importer and rejected on the same grounds a pasted response would be
- [x] #3 The existing prompt-and-paste path still works unchanged as a fallback
- [x] #4 Evaluating a selection is dry-run by default and reports per job what it would create or update before anything is written
- [x] #5 A provider or validation failure names the real error and never leaves a job partially updated
- [x] #6 Synthetic regressions cover an accepted response, a rejected malformed response, and the dry-run preview, without calling a real provider
<!-- AC:END -->

## Verification
<!-- SECTION:NOTES:BEGIN -->
Measured on the owner's machine on 2026-09-08, against the real board at localhost:8000.

**AC1/AC4 end to end, with a real provider.** One job (Magenta Telekom) evaluated through
provider `anthropic`, model `haiku`, from inside the app with no copy-paste. Returned in **79s**.
The preview rendered `86 | high | apply | Replaces current fit 94`, under the banner "Preview only,
nothing has been saved yet". `/api/stats/` `average_fit_score` was `62.169642857142854` before and
after — **nothing was written**. The dialog was then closed without saving.

**The commit click was deliberately not pressed.** localhost runs against the production database
(TASK-111), so pressing Save would have replaced a genuine fit-94 evaluation with haiku's 86 on a
real lead. The write path is covered by `test_accepted_response_is_written_only_when_the_caller_commits`
instead. Someone who wants the click exercised should do it on a throwaway lead.

**AC5 observed for real, not only in tests.** The first attempt used `ollama`/`gemma3:4b`; it failed
in 36s, Save stayed disabled, the board was unchanged, and the real provider text was shown rather
than a generic message.

### Blocker found, pre-existing and NOT introduced here

`codex exec --oss --local-provider ollama` does not work on this machine, for two independent
reasons, both reproduced directly on the command line outside the app:

1. `gemma3:4b does not support tools` — `codex exec` requires a tool-capable model, so several
   installed ollama models cannot be used at all.
2. With the tool-capable `gpt-oss:20b`, codex fails to read ollama's model list:
   `failed to decode models response: missing field 'models'` — ollama answers with an OpenAI-style
   `data` array, which this codex build does not accept.

This is the same command `generate_cv_package` builds, so **CV generation through ollama is equally
broken on this machine today** — this task did not cause it and cannot fix it from here. The
practical consequence is that the task description's "Ollama keeps it free" premise does not hold on
this machine right now; the working providers are `anthropic` and `openai`, both of which bill.
Worth its own task.

### Quality issue worth a follow-up, not a blocker

On the ollama failure the surfaced `detail` was the tail of the **echoed prompt**, not the
`ERROR: ... does not support tools` line that actually explained it. AC5 is still met — the text is
the provider's own output, not a generic message — but `run_structured_model`'s `[-6000:]` tail
slice can bury the actionable line when the CLI echoes a long prompt. Preferring stderr lines that
look like errors would fix it, in `cv_generator.run_structured_model`, and would change CV
generation's error text too, so it belongs in its own task rather than here.
<!-- SECTION:NOTES:END -->
