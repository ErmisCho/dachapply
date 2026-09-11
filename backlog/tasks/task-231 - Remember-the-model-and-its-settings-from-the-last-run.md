---
id: TASK-231
title: Remember the model and its settings from the last run
status: Done
assignee: []
created_date: '2026-09-11 11:20'
updated_date: '2026-09-11 20:26'
labels:
  - frontend
dependencies: []
priority: high
ordinal: 230000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner request 2026-09-11. The model and its settings should be remembered between runs.

Today they are not. CvGenerator (App.tsx:587) resets them on every mount from whatever the API happens to list first:

    setProvider(p.models?.[0]?.provider||"openai"); setModel(p.models?.[0]?.key||"");
    setEffort(modelEffort(p.models?.[0])); setSpeed(modelSpeed(p.models?.[0]))

So every time the popup opens, the selection reverts to the first entry in the discovery order, and the owner re-picks. The repo already persists per-user UI state in localStorage under `dachapply_*` keys (theme, onboarding), so the pattern exists.

Two things a naive implementation gets wrong, and both have bitten this repo before: a remembered model that is no longer installed (LM Studio models come and go - TASK-221) must not leave the popup in an unusable state, and a remembered effort/speed combination that the remembered model does not support must not silently produce an invalid request - `comboValid()` already exists for exactly that check.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Reopening the popup restores the provider, model, effort and speed used last time, verified across a full page reload rather than within one session
- [x] #2 A remembered model that is no longer offered falls back to a valid selection instead of leaving the popup broken or sending an unusable request
- [x] #3 A remembered effort or speed the remembered model does not support is corrected rather than sent - `comboValid` is the existing gate
- [x] #4 Nothing is remembered across accounts: the stored selection is scoped so a different user does not inherit it
- [x] #5 Frontend tests cover restore, the missing-model fallback and the invalid-combo correction, and the result is verified in the served bundle at localhost:8000
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
## Done 2026-09-11

Stored per account at `dachapply_cv_picks_<email>` as one JSON object holding both pickers, read after
discovery lands and written only once `preview` exists, so pre-load defaults can never overwrite a
good saved value.

Verified across a FULL page reload, not just a remount: generate came back as
`Anthropic Claude - sonnet - medium` and adjust as `OpenAI Codex - gpt-5.6-sol - low - 1.5x`, matching
what was stored.

All three traps route through one resolver, `cvPick(models, want)`, which every path calls - restore,
provider change, model change, effort change, speed change. A model that is gone falls back to its
provider first entry then to the first offered; an unsupported effort or speed is replaced by the
resolved model default. Reads and writes are wrapped, because localStorage throws rather than
returning null in private mode. The old normalising effect that corrected effort after the fact is
gone - it was a second place the same rule lived.
<!-- SECTION:NOTES:END -->
