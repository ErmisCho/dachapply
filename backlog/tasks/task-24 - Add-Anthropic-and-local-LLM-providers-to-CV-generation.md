---
id: TASK-24
title: Add Anthropic and local LLM providers to CV generation
status: Done
assignee:
  - '@pi'
created_date: '2026-07-15 15:22'
updated_date: '2026-07-15 15:33'
labels:
  - frontend
  - backend
  - ai
dependencies:
  - TASK-23
priority: medium
ordinal: 24000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The local CV generator discovers and offers OpenAI Codex, Claude Code subscription aliases, installed Ollama models, and installed LM Studio models. Provider-specific capabilities constrain effort and speed choices.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Provider and model selectors include OpenAI, Anthropic when Claude CLI is installed, Ollama models, and LM Studio LLMs
- [x] #2 Local model lists are discovered from installed provider CLIs without hardcoding model names
- [x] #3 OpenAI uses Codex subscription settings, Anthropic uses Claude Code structured output, and local models use Codex OSS provider mode
- [x] #4 Effort and 1.5x Fast appear only when supported by the selected provider/model
- [x] #5 Backend validation prevents mismatched provider/model settings
- [x] #6 Tests cover provider discovery and command construction
- [x] #7 Effort and Speed selectors are visibly disabled and cannot open when the selected model has no alternative
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Extend model discovery with provider metadata and local CLI discovery. 2. Add Provider selector and filter model capabilities. 3. Route generation through Codex, Claude Code, or Codex OSS commands. 4. Carry provider through async tasks. 5. Add focused tests and build checks.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Added provider-aware discovery and execution. Current local discovery returns 6 OpenAI, 3 Anthropic aliases, 16 Ollama, and 4 LM Studio models. Claude uses print mode with Read-only tools and JSON Schema; Ollama/LM Studio use Codex OSS local-provider mode; OpenAI retains effort/Fast controls. Non-OpenAI providers expose only applicable default effort and Normal speed. Validation: 106 backend tests, frontend build, and Django checks passed. Existing demo scheduler startup traceback remains unrelated.

Disable single-option capability selectors instead of presenting inert dropdowns.

Effort is disabled when the selected model exposes one effort; Speed is disabled when Fast is unsupported. Disabled selectors are gray, remove the dropdown arrow, use a not-allowed cursor, and cannot open. Frontend build passed.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
The CV generator now offers OpenAI Codex, Anthropic Claude Code, installed Ollama models, and installed LM Studio LLMs through provider-aware selectors and validated execution paths.

Single-option Effort and Speed controls are now visibly disabled and non-interactive.
<!-- SECTION:FINAL_SUMMARY:END -->
