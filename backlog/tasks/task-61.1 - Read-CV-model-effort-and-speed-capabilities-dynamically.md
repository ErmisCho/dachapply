---
id: TASK-61.1
title: Read CV model effort and speed capabilities dynamically
status: Done
assignee:
  - '@claude'
created_date: '2026-08-13 19:30'
updated_date: '2026-08-14 16:05'
labels:
  - cv-generation
  - providers
  - bug
dependencies: []
parent_task_id: TASK-61
priority: high
ordinal: 63000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Fix CV generation with Anthropic Claude and other providers so effort and speed controls come from the selected model's reported capabilities rather than hard-coded OpenAI assumptions. Anthropic must remain runnable; options such as fast speed should appear only for models that actually support them, including any Opus-only restriction reported by the provider.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Selecting any configured Anthropic Claude model produces a valid CV-generation request and can start generation
- [x] #2 Effort choices, speed choices, defaults, and enabled states are derived from backend/provider model capability metadata for the currently selected model
- [x] #3 Unsupported effort or speed combinations cannot be submitted and produce a concise actionable error if sent directly to the API
- [x] #4 Switching provider or model immediately resets stale values to a supported combination
- [x] #5 Backend and frontend tests cover Anthropic plus at least one model with and one model without a fast tier
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Extracted validate_model_capability(provider, model, effort, speed) in cv_generator.py and called it synchronously from generate_cv_documents and revise_latest_cv_documents, so unsupported combinations now return 400 with an actionable message instead of 202-then-fail-later. Frontend already derived options from selectedModel.efforts / fast_tier and already reset on provider AND model change; added self-correction so a stale effort/speed value not in the current model's valid set is fixed without waiting for a change event, plus submit blocking. Anthropic (efforts:['default'], fast_tier:'') verified runnable at normal speed and correctly rejected at fast speed. AC5 DONE (2026-08-14): backend coverage was already there (test_validate_model_capability_accepts_anthropic_normal_speed_and_rejects_its_fast_speed, test_cv_generation_starts_task_for_anthropic_model_but_rejects_its_fast_speed, plus test_cv_generation_rejects_unsupported_capability_combinations covering gpt-5.5 with a fast tier and gpt-5.4-mini without). Frontend coverage now exists: added vitest (one devDependency, "test":"vitest run") and extracted the capability rules out of App.tsx into frontend/src/cvModel.ts (modelEffort / modelSpeed / comboValid / stepText) so they are testable without a DOM - no jsdom or testing-library needed. The extraction also removed the duplicated comboInvalid expression that was copy-pasted into CvGenerator and BatchCvGenerator. frontend/src/cvModel.test.ts covers Anthropic (efforts ['default'], fast_tier '') accepted at normal speed and rejected at fast, gpt-5.5 (with fast tier) accepted at fast, gpt-5.4-mini (no fast tier) rejected at fast, and stale-effort rejection. 8 frontend tests pass; npx tsc --noEmit is clean.

Note carried into TASK-61 review: the three Anthropic entries in available_model_options() (cv_generator.py:146-148) are static literals with identical capabilities, so there is no Opus-specific fast-tier distinction. AC2 as written is met (the frontend derives everything from backend metadata), but the description's "any Opus-only restriction reported by the provider" is not modelled - revisit if the Claude CLI ever reports per-model tiers.
<!-- SECTION:NOTES:END -->
