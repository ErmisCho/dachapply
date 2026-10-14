---
id: TASK-290
title: Model lists discover the latest models and their effort and speed everywhere
status: To Do
assignee: []
created_date: '2026-10-14 09:01'
labels: []
dependencies: []
ordinal: 291000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner (2026-10-14): every model picker (CV generation, draft chat, follow-up draft, evaluation) must show the latest models, e.g. GPT-6 and GPT-6.1, and offer effort and speed only where the model supports them. Measured: codex_model_options() in cv_generator.py already reads ~/.codex/models_cache.json dynamically, but the installed Codex CLI is 0.146.0 (latest 0.162.1) and its cache (fetched 2026-10-14) lists only gpt-5.6-sol/terra/luna as visible, so the server likely sends newer models only to newer clients. FALLBACK_MODELS is a hard-coded list.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 With the current Codex CLI, every model picker lists the models Codex offers (GPT-6 and GPT-6.1 if Codex lists them), newest first; nothing hard-coded hides them
- [ ] #2 Effort choices and the fast/speed option are offered per model from what the model declares (supported_reasoning_levels, service_tiers; Claude --effort), and hidden where not applicable
- [ ] #3 The Codex CLI upgrade path is documented or automated, with the owner's OK before installing anything
- [ ] #4 FALLBACK_MODELS is only used when discovery fails, and says so in the picker
- [ ] #5 Tests cover discovery from a models cache containing new models and per-model effort/speed options
<!-- AC:END -->
