---
id: TASK-225
title: Bound the append-only learned application preferences
status: In Progress
assignee: []
created_date: ''
updated_date: '2026-09-10 12:14'
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
- [x] #1 The growth is bounded by a stated rule — a cap, an age-out, a summarisation step, or per-scope selection — chosen from measured evidence about which preferences are still used rather than from whichever is easiest to implement
- [x] #2 Whatever bound is chosen, the size after it is applied is reported by `manage.py report_cv_prompt_size` so the effect is visible rather than asserted
- [x] #3 Existing learned preferences are not silently discarded: whatever is dropped from the prompt is still recoverable by the owner, or its removal is something they explicitly approved
- [x] #4 Output quality is compared before and after on the same job — TASK-224 deliberately trimmed nothing, so this is the first change that must prove it does not make the documents worse
- [x] #5 A regression covers the bound without calling a provider, and fails if the bound is removed
- [x] #6 The per-day growth rate is re-measured after the change, to show the bound actually holds rather than merely resetting the number once
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Branch `task-225-bound-learned-preferences`. Sealed rubric at `.claude/.asian-dad/task-225-rubric.json` (gitignored, written before any implementation per TW-001).

## The measurement contradicted this task own premise

The description guessed at a long tail of small entries and pointed at the casefold dedup. Measured
against the real field with the new `report_cv_prompt_size --learned`, neither is true:

| | measured 2026-09-10 |
|---|---|
| entries | **40** (not hundreds) |
| shortest / median / p90 / longest entry | 67 / **1,521** / 4,960 / **4,979** chars |
| duplication exact-casefold dedup missed | **234 chars, 0.2%** |
| a fuzzy (90% difflib) rule would remove | 1 further entry |

The longest entries sit right against the `instructions[:5000]` truncation in `views.py`, i.e. they
are whole pasted readjustment briefs, not one-line preferences. Better dedup would have bought 0.2%.

**That is what chose the rule (AC1).** Entry lengths span 67-4,979 chars, a 74x spread, so a cap on
entry COUNT does not bound what the field costs: last-10 could be ~670 chars or ~49,790 depending on
which ten. A cap on CHARACTERS does. The rule is therefore a **newest-first character budget**,
`CODEX_LEARNED_PREFERENCES_BUDGET`, default 16,000, applied in `cv_generator.bound_learned_preferences`
and wired into `load_candidate_evidence` - the single chokepoint both `views.py:1966` and
`views.py:2039` already route through. Floor: the newest entry is always sent, even alone over
budget. `budget<=0` is unbounded and byte-identical to the old behaviour.

## Effect, measured on the real database (AC2)

`manage.py report_cv_prompt_size` reports the post-bound number because it calls the same helper, so
the report and generation cannot disagree:

| | before | after |
|---|---|---|
| learned preferences in the prompt | 89,743 chars / 58.9% | **15,846 chars / 20.2%** |
| whole CV prompt | 152,452 chars / ~38,113 tokens | **78,586 chars / ~19,646 tokens** |

A **48.5%** cut to every CV request, on every provider, on all three attempts of a failure.

## Nothing was deleted (AC3)

The stored field is never written. All 93,243 chars remain in `UserProfile.learned_application_preferences`,
readable and editable in account settings exactly as before; 77,397 of them are simply not sent. No
migration and no pruning command exists, so there is nothing to dry-run. The report prints the gap so
it cannot go unnoticed, and the prompt header changes from the old wording to "most recent 9 of 42
entries" so the model is not told a partial list is complete.

## Quality compared before and after, with a control (AC4)

Job 1488, anthropic/sonnet, effort medium, three real generations:

| comparison | similarity | diff lines |
|---|---|---|
| unbounded vs bounded | 98.1% | 17 |
| **unbounded vs unbounded (control)** | **97.6%** | **13** |

Two runs of the identical prompt differ MORE than bounded differs from unbounded. So the bound does
not systematically degrade the document - its effect is inside the model own run-to-run variation.
The control is what makes that a measurement rather than an impression.

Two of the three differences (headline, professional summary) also move in the control, so they are
the model. **The third does not**, and it changed a factual claim about a past role. Tracing it found
that such claims live only in this append-only field and not in `candidate_evidence`, which the
pipeline treats as authoritative. That is a real risk this bound exposes but did not create, and it is
filed as **TASK-229** rather than hidden here.

## The bound is falsifiable (AC5)

`backend/jobradar/tests/test_learned_preferences.py`, 9 tests, no provider launched. Falsified by
neutralising the wiring:

    AssertionError: assert 250049 <= 16000

Restored, green again. A second falsification was needed on the reporting side: wiring the bound in
made `prompt_chars` the BOUNDED prompt, which inverted every share denominator in the `--learned`
tables - they printed **-375.6%** before it was caught. Fixed, and pinned by
`test_no_share_column_can_read_negative_or_over_a_hundred`, itself falsified against the old
expression.

## Growth re-measured, with the bound live (AC6)

| moment | stored entries | stored chars | chars actually SENT |
|---|---|---|---|
| 2026-09-09, task filed | - | 85,004 | 85,004 |
| 2026-09-10, task filed | - | 89,675 | 89,675 |
| 2026-09-10, first measurement, pre-bound | 40 | 89,743 | 89,743 |
| 2026-09-10, after the bound | **42** | **93,243** | **15,846** |

The field grew by 2 entries and 3,500 chars during this session from the owner own use - the scope
split moved 17 -> 19 on `- [CV + letter]`, and no run made here appends (a plain generation passes
empty `revision_instructions`). Storage keeps growing, which is the design: nothing is deleted. What
the prompt carries did not move, and structurally cannot exceed the budget. That is the difference
between resetting a number once and a bound that holds.

## Verified in the running app

One real generation for job 1488 driven through the app own HTTP endpoint (`/api/jobs/1488/cv-generation/run/`)
with the bound live: **ready in 148s, CV TeX produced, 0 repair attempts**. Backend suite **1127
passed** (baseline 1084). No frontend file changed, so the served bundle is unaffected.

## Worth the owner attention

The whole request is now ~19,646 estimated prompt tokens plus 2,981 for the template read and codex
own 9,448 - about 32k estimated, and roughly 29k at the 4.7 chars/token ratio LM Studio own tokenizer
actually measured. TASK-221 AC4 was blocked because the request was 40,654 tokens against a 32,768
ceiling. It may now fit. Not claimed - not measured against a local model - but it is the first time
it is worth trying.

## Independent verification by the coordinator (TW-003), after the agent reports

The implementing agent reported its own falsification. That is evidence, not proof, so both
load-bearing claims were re-checked here rather than taken on its word:

**The bound test really is falsifiable.** Neutralised the call site independently
(`bound_learned_preferences(learned_preferences, 0)`) and re-ran:

    FAILED test_over_budget_header_states_the_most_recent_n_of_m
    FAILED test_load_candidate_evidence_actually_bounds_the_prompt
    2 failed, 7 passed

Restored; 9 passed. No probe residue in the staged diff.

**The readjustment path was verified separately from generation**, because it is the path that
WRITES this field and so the one most likely to break. Driven through the app own endpoint
`/api/jobs/1488/cv-generation/revise-latest/` with real instructions:

- **ready in 70s, CV TeX produced, 86 chars appended** to the learned preferences.

That single run is also the cleanest AC6 evidence available, because it is growth caused on purpose
and watched:

| | entries | stored chars | chars SENT |
|---|---|---|---|
| before the readjustment | 42 | 93,243 | 15,846 |
| after it | **43** | **93,330** | **15,933** |

The field grew, the prompt did not follow it past the budget, and the report now says "the newest 10
of 43 entries". The stored side keeps growing by design; the paid side no longer tracks it.

## One defect found and fixed during verification, not by the tests

Wiring the report to the bound made `prompt_chars` the BOUNDED prompt, which inverted every share
denominator in the `--learned` tables. It printed **-375.6%** on real data. Nothing in the suite
caught it - the tables had only ever been exercised under the budget. Fixed by computing every share
against the prompt as it would be with nothing dropped, and pinned by a test that was itself
falsified against the old expression.

## Scanned before committing

The repository is PUBLIC. The staged diff was grepped for evidence, CV and preference content: clean.
TASK-229 was rewritten term-free for the same reason before it was staged - its first draft named the
competing wordings, which is exactly the owner career data this task measures the LENGTH of and never
prints.
<!-- SECTION:NOTES:END -->

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
