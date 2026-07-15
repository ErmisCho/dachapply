---
id: TASK-23
title: 'Add Codex model, effort, and speed controls'
status: Done
assignee:
  - '@pi'
created_date: '2026-07-15 15:05'
updated_date: '2026-07-15 15:14'
labels:
  - frontend
  - backend
  - ai
dependencies:
  - TASK-22
priority: medium
ordinal: 23000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The local CV generator lets the owner choose an available Codex model, supported reasoning effort, and normal or 1.5x Fast service before starting an asynchronous task.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Generation preview exposes locally available Codex models and their supported effort/speed options
- [x] #2 The UI provides Model, Effort, and Speed selectors with compatible defaults
- [x] #3 Changing model resets unsupported effort or Fast selections
- [x] #4 The backend validates selections and passes model_reasoning_effort plus Fast service tier to Codex
- [x] #5 Tests verify Codex CLI arguments and option validation
- [x] #6 The model selector includes the current GPT-5.6 Sol, Terra, and Luna options with their live supported efforts
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Read the local Codex model cache with a small fallback catalog. 2. Expose model capabilities in preview. 3. Add selectors and compatibility behavior. 4. Carry validated options through the async task into Codex CLI. 5. Run focused tests and frontend build.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Read available models, efforts, and Fast tier from the local Codex models cache with a small fallback catalog. Added Model, Effort, and Speed controls; model changes reset effort and speed to compatible defaults. Validated all values in the generation service and passed --model, model_reasoning_effort, and service_tier=priority for 1.5x Fast. Validation: 105 backend tests, frontend build, and Django check passed. Existing demo scheduler startup traceback is unrelated.

Updated local Codex from 0.140.0 to 0.144.4 and refreshed the authenticated model catalog; it now exposes GPT-5.6 Sol, Terra, and Luna.

Updated Codex CLI to 0.144.4 and refreshed its authenticated model cache through app-server model/list. The live cache now supplies GPT-5.6-Sol (low through ultra), GPT-5.6-Terra (low through ultra), and GPT-5.6-Luna (low through max), all with 1.5x Fast. Added the same entries to the no-cache fallback. Three focused tests and Django checks passed.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
The local CV generator now supports available Codex model selection, compatible reasoning effort, and Normal or 1.5x Fast speed. Selections flow through the async task and are validated before Codex execution.

The selector now includes the live GPT-5.6 Sol, Terra, and Luna catalog and automatically follows future locally cached model updates.
<!-- SECTION:FINAL_SUMMARY:END -->
