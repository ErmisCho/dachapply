---
id: TASK-61.1
title: Read CV model effort and speed capabilities dynamically
status: To Do
assignee: []
created_date: '2026-08-13 19:30'
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
- [ ] #1 Selecting any configured Anthropic Claude model produces a valid CV-generation request and can start generation
- [ ] #2 Effort choices, speed choices, defaults, and enabled states are derived from backend/provider model capability metadata for the currently selected model
- [ ] #3 Unsupported effort or speed combinations cannot be submitted and produce a concise actionable error if sent directly to the API
- [ ] #4 Switching provider or model immediately resets stale values to a supported combination
- [ ] #5 Backend and frontend tests cover Anthropic plus at least one model with and one model without a fast tier
<!-- AC:END -->
