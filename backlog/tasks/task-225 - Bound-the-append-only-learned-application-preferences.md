---
id: TASK-225
title: Bound the append-only learned application preferences
status: To Do
assignee: []
labels:
  - backend
  - llm
  - cost
dependencies: []
priority: high
ordinal: 224000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Filed 2026-09-10 from TASK-224's measurement. `UserProfile.learned_application_preferences` is
**append-only and unbounded**, and it is now the largest single component of every CV generation
request — **89,675 characters, ~22,419 tokens, 59.1% of the prompt.**

`cv_tasks.py:249` adds one line per learned preference, deduplicated by casefold but never pruned,
never summarised, never aged out:

    profile.learned_application_preferences='\n'.join([*lines,entry]).strip()

It measured **85,004** chars on 2026-09-09 and **89,675** on 2026-09-10 — about **4,700 characters
added in a single day of normal use**, roughly 1,175 tokens per day, growing forever.

For contrast, in the same request the job description — the only part that differs between one
generation and the next — is **3,953 characters**, and on a short posting it was **205**.

### Why this matters beyond tidiness

- It is paid on **every** provider, on **every** attempt. A failed generation makes three attempts,
  so the accumulated history is charged three times for output that never arrives (TASK-224 measured
  the whole failure at ~154,200 tokens).
- It is the reason local CV generation is out of reach. TASK-221 established that a tool-capable
  local model is needed; the tool-capable ones tend to cap at 32k context, and this component alone
  is two thirds of that budget.
- The growth is silent. Nothing in the UI or the prompt shows its size, and nobody would have found
  it without a provider refusing the request outright.

### What is NOT yet known

Whether old preferences still earn their place. A preference learned for a Django role in March may
be actively unhelpful for an AI-platform role in September, so this is not purely a cost question —
it may also be diluting the instructions that matter. That should be established before choosing a
strategy, not assumed.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The growth is bounded by a stated rule — a cap, an age-out, a summarisation step, or per-scope selection — chosen from measured evidence about which preferences are still used rather than from whichever is easiest to implement
- [ ] #2 Whatever bound is chosen, the size after it is applied is reported by `manage.py report_cv_prompt_size` so the effect is visible rather than asserted
- [ ] #3 Existing learned preferences are not silently discarded: whatever is dropped from the prompt is still recoverable by the owner, or its removal is something they explicitly approved
- [ ] #4 Output quality is compared before and after on the same job — TASK-224 deliberately trimmed nothing, so this is the first change that must prove it does not make the documents worse
- [ ] #5 A regression covers the bound without calling a provider, and fails if the bound is removed
- [ ] #6 The per-day growth rate is re-measured after the change, to show the bound actually holds rather than merely resetting the number once
<!-- AC:END -->

## Notes
<!-- SECTION:NOTES:BEGIN -->
Measure the current state first:

    cd backend
    export DJANGO_SETTINGS_MODULE=config.settings
    export DACHAPPLY_ALLOW_PROD_DB=1
    uv run python manage.py report_cv_prompt_size

Per CLAUDE.md, a bulk data change to the stored preferences gets a **dry-run-by-default management
command**, never a migration, so the owner can inspect what would be dropped before anything is
written. AC3 is that rule restated for this task.
<!-- SECTION:NOTES:END -->
