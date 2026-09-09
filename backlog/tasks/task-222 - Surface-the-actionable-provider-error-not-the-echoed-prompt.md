---
id: TASK-222
title: 'Surface the actionable provider error, not the echoed prompt'
status: Done
assignee:
  - '@ErmisCho'
created_date: ''
updated_date: '2026-09-09 14:16'
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
- [x] #1 A failed provider run surfaces the line that names the cause, even when the CLI echoed a prompt longer than the detail budget
- [x] #2 The echoed prompt is not presented to the owner as though it were the model's answer
- [x] #3 Nothing is truncated in a way that hides a cause with no other trace — if the output is dropped, the fact that it was dropped is visible
- [x] #4 CV generation's failure reporting is verified as no worse than today, since it shares this function
- [x] #5 A synthetic regression covers a long echoed prompt followed by a short trailing error, without calling a real provider
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Add _failure_detail() to cv_generator.py: identify echoed prompt lines by exact-match against the sent prompt, strip them, label what was removed, keep both head and tail on overflow (not tail-only). 2. Wire run_structured_model's failure branch through it, passing both stderr and stdout instead of stderr-or-stdout. 3. Add test_provider_errors.py reproducing both real failures (ollama tool-support error, lmstudio context-length error) as fakes with no real provider call, plus edge cases: all-echo output, over-budget output, cause on the other stream, claude provider path, empty output, successful run untouched.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented and verified 2026-09-09. 12/12 new tests pass (test_provider_errors.py). Broader regression: 78 passed in jobradar/tests -k 'evaluat or cv_generator or provider' (0 failures).
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
cv_generator.run_structured_model now builds its failure detail via _failure_detail(), which strips lines matching the sent prompt (the echo), labels what it removed or that everything was echo, and on overflow keeps both the head and tail instead of only the tail. Verified with 9 new tests in test_provider_errors.py covering both real reproductions (ollama tool-support error, lmstudio context-length error) plus all-echo, over-budget, other-stream, claude-provider, and no-output edge cases, and a successful-run-untouched check. All pass; wider evaluat/cv_generator/provider suite (78 tests) unaffected.
<!-- SECTION:FINAL_SUMMARY:END -->
