---
id: TASK-222
title: Surface the actionable provider error, not the echoed prompt
status: To Do
assignee: []
labels:
  - backend
  - llm
  - errors
dependencies: []
priority: medium
ordinal: 221000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Filed 2026-09-08 from TASK-220's verification. `cv_generator.run_structured_model` reports a failed
provider run as `(result.stderr or result.stdout)[-6000:]` — the last 6000 characters. When the CLI
echoes the prompt back, and this project's prompts are long, that tail is prompt text and the line
that actually explains the failure is pushed out of the window.

Observed for real: an ollama run failed with `ERROR: ... does not support tools`, and what the owner
was shown in the dialog was a slab of the evaluation prompt's own "job matching rules" section. The
message was genuinely the provider's own output rather than a generic one, so it was not wrong — it
was just useless, which for an error message is close enough to the same thing.

This is shared code, so a change here alters CV generation's error text as well as evaluation's,
which is why it was not done inside TASK-220.

**Reproduced on the CV path too, 2026-09-09** (TASK-221 verification), which settles AC4's premise
that this function's behaviour is shared. CV generation through
`lmstudio / deepseek-r1-distill-qwen-7b` failed with *"The selected model could not complete the
request. Two automatic repair attempts also failed."*, and expanding **Technical details** showed:

    Attempt 1: The selected model could not complete the request.
    g ingestion and search reliability, evaluating retrieval quality, or creating production-minded
    AI applications. ... What to penalize ...

— the evaluation prompt's own rules section, cut mid-word, with no trace of the real cause. The real
cause was that the model never called the file-reading tool and echoed the prompt back instead. So
this defect is not ollama-specific and not evaluation-specific: any provider that echoes a long
prompt produces it.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A failed provider run surfaces the line that names the cause, even when the CLI echoed a prompt longer than the detail budget
- [ ] #2 The echoed prompt is not presented to the owner as though it were the model's answer
- [ ] #3 Nothing is truncated in a way that hides a cause with no other trace — if the output is dropped, the fact that it was dropped is visible
- [ ] #4 CV generation's failure reporting is verified as no worse than today, since it shares this function
- [ ] #5 A synthetic regression covers a long echoed prompt followed by a short trailing error, without calling a real provider
<!-- AC:END -->
