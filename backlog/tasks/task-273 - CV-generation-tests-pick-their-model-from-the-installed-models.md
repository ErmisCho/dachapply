---
id: TASK-273
title: CV generation tests pick their model from the installed models
status: Done
assignee: []
created_date: '2026-10-07 15:00'
labels:
  - backend
  - tests
dependencies: []
priority: medium
ordinal: 270000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Four test_api.py tests fail on the owner's machine with 400 "Select an available model for the chosen provider.":
- test_cv_generation_starts_asynchronously
- test_cv_task_status_and_download_are_owner_only
- test_cv_capability_flag_opens_generation_to_a_non_owner_and_defaults_closed
- test_cv_generation_uses_the_requesting_users_stored_evidence

They hardcode `gpt-5.5`, but the run endpoints validate against `available_model_options()`. That reads `~/.codex/models_cache.json`, which on this machine now lists only gpt-5.6-*. CI has no cache and falls back to FALLBACK_MODELS, so the tests pass there.

Owner decision 2026-10-07: "it's good to have a baseline, so pick from the llms that are installed on this machine for the tests". The tests use a model taken from the installed options instead of a hardcoded name.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The four tests take provider, model and effort from `available_model_options()` (an installed openai model, with an effort it supports, and fast only if it has a fast tier) instead of hardcoding gpt-5.5. Their assertions use the chosen values
- [x] #2 The full backend suite passes on the owner's machine (0 failures) and in CI
- [x] #3 The tests still fail when the behaviour they check is broken: mutation-check at least one of the four
- [x] #4 No production code changes
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
- `_installed_openai_pick(effort)` in test_api.py takes the first openai entry from `available_model_options()`. Effort is the requested one if supported, otherwise the model default. Speed is `fast` only when the model has a fast tier. The four tests use it in their payloads and assertions. On this machine it picks gpt-5.6-sol; in CI it picks from FALLBACK_MODELS. The conftest autouse fixture already resets the 60 s options cache.
- Mutation: forcing speed `normal` in the run view fails test_cv_generation_starts_asynchronously.
- AC2: a full suite on the owner's machine via `python -m pytest`, after TASK-274: 1369 passed, 0 failed. Before TASK-274, runs failed 21 and 30 mailbox tests that this change does not touch. That cause is filed and fixed separately as TASK-274.
<!-- SECTION:NOTES:END -->
