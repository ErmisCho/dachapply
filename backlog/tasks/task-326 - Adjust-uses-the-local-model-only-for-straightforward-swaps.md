---
id: TASK-326
title: Adjust uses the local model only for straightforward swaps
status: Done
assignee: []
created_date: '2026-10-21 08:53'
updated_date: '2026-10-21 09:03'
labels:
  - backend
dependencies: []
priority: medium
ordinal: 326000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner 2026-10-21 (screenshot: a multi-paragraph layout request showed 'Reading the edit with gemma3:4b' before GPT-6.1-Sol started): 'the local model should be used for only straight forward things' / 'it should be used for swaps only that are straight forward'. Today every Adjust instruction the deterministic parser cannot read is first sent to the local model (TASK-278), which can only refuse a rewrite request and costs up to CODEX_CV_LITERAL_EDIT_TIMEOUT (30 s) before the chosen model starts.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The local model is asked only when the instruction is a short swap: at most 3 non-blank lines, at most 300 characters, and no rewrite words (make, shorten, concise, improve, rewrite, translate, fit, layout, page, add, remove, ...)
- [x] #2 Any other instruction the deterministic parser cannot read goes straight to the chosen model, with no local-model step and no wait
- [x] #3 Exact OLD:/NEW: blocks and the deterministic replace/change/-> parser are unchanged
- [x] #4 The TASK-278 gate still guards every local-model answer; a short swap the model gets wrong still falls back as today
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Merged in #317. test_literal_edits.py 34 passed: the owner's multi-paragraph layout request, a swap mixed with 'make ... more concise' and a rewrite request start the chosen model with no local-model call; 'My phone number is now ...' still goes to the local model and is applied; the gate still refuses a partial claim ('... and mention Kubernetes'). CI green. Localhost relaunched on ef792e1 (no migration). Not run live: a live Adjust would spend a real model run on a CV.
<!-- SECTION:NOTES:END -->
