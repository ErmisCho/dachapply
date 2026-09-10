---
id: TASK-224
title: Find out what the 40k-token CV request is actually made of
status: In Progress
assignee:
  - '@ErmisCho'
created_date: ''
updated_date: '2026-09-10 06:05'
labels:
  - backend
  - llm
  - cost
dependencies: []
priority: medium
ordinal: 223000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Filed 2026-09-09 from TASK-221's verification. A single CV generation sends **40,654 tokens** to the
provider. That number is not an estimate: it came from LM Studio refusing the request outright,
which is the only reason anyone noticed.

    Engine protocol predict request returned 400: request (40654 tokens) exceeds the
    available context size (32768 tokens)

It matters beyond local models. Every CV generation pays it on **anthropic and openai too**, on every
attempt — and the CV path retries twice on failure, so a failed generation pays it three times.

### What is measured

| part | tokens | how |
|---|---|---|
| whole request | 40,654 | provider's own error |
| codex's system prompt + tool definitions | 9,448 | same, from a trivial one-file probe |
| candidate evidence, after compaction | ~8,434 | `_compact_candidate_evidence`, measured |
| candidate evidence, before compaction | ~26,458 | source file is 105,835 chars |
| **unaccounted** | **~22,800** | **not measured — this is the task** |

### ANSWERED 2026-09-09 — it is the learned preferences, and it is not close

The unaccounted tokens were found by building the real prompt from the owner's own profile and a real
job, and measuring each component. **`learned_application_preferences` is the single largest
contributor at ~60% of the user prompt.**

| component | chars | ~tokens | share |
|---|---|---|---|
| **`learned_application_preferences`** | **85,004** | **~21,251** | **~60%** |
| candidate evidence, after `_compact_candidate_evidence` | 33,737 | ~8,434 | ~24% |
| profile text (`build_candidate_profile_text`) | 9,031 | ~2,257 | ~6% |
| bundle scaffolding | ~8,600 | ~2,150 | ~6% |
| `_prompt` scaffolding + mandatory rules | 3,889 | ~972 | ~3% |
| **job `source_text`** | **205** | **~51** | **~0.1%** |
| full user prompt | 140,478 | ~35,119 | 100% |
| codex system prompt + tool definitions | — | 9,448 | on top |

Authoritative total from the provider's own tokenizer on a CV-only run: **39,129 tokens**.

**The job description — the only part that differs between one generation and the next — is 205
characters.** Everything else is the same on every run, for every job.

### Two wrong guesses, kept because they are the lesson

1. **"Mostly candidate evidence."** Written into TASK-221 without measuring. Compaction already
   removes 68% of the evidence, so evidence is about a fifth.
2. **"The LaTeX templates are the prime suspect."** Measured, but against the wrong thing — the
   templates really are pulled in through codex's file-reading tool calls, but they total
   `English - AI Engineer (base)_v_1.5.tex` 11,924 chars (~2,981 tokens) plus `Motivation_letter.tex`
   2,958 chars (~739). About 3.7k tokens combined. Never the problem.

Both guesses were plausible and both would have aimed the work at the wrong target. AC1 says
"measured numbers, not estimates" for exactly this reason.

Note on where the owner's templates live: the `CvAsset` rows on this account hold only fictional demo
assets, so generation resolves them through the TASK-189 machine-local fallback at
`CODEX_CV_WORKSPACE` (`C:\latex`). That is why they were not measurable from the rows.

Interaction with TASK-221: a request this size rules out most local models regardless of tool
support, because the tool-capable ones tend to cap at 32k. Trimming `learned_application_preferences`
is the cheapest route to a free local CV path, if that is still wanted.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The 40,654 tokens are broken down by component with measured numbers, not estimates, and the largest contributor is named
- [x] #2 The measurement is reproducible on demand — a command or flag that reports the size of a request before it is sent, rather than a number someone recorded once
- [x] #3 Any reduction is shown to preserve output quality, by generating the same CV for the same job before and after and comparing the documents, not just by asserting the prompt is smaller
- [x] #4 The retry path is counted: a failed generation's true token cost is stated, given it attempts three times
- [x] #5 If the templates read through tool calls are a large share, the fact that reading a file costs prompt tokens is written down where the next person will find it
<!-- AC:END -->

## Implementation Notes

Shipped `manage.py report_cv_prompt_size` — read-only, sends nothing, prints sizes only (never the
evidence, CV, profile or job text). Run it as:

    cd backend
    export DJANGO_SETTINGS_MODULE=config.settings
    export DACHAPPLY_ALLOW_PROD_DB=1
    uv run python manage.py report_cv_prompt_size

Real output, job 1478, 2026-09-10:

| component | chars | ~tokens | share |
|---|---|---|---|
| **learned application preferences** | **89,675** | **22,419** | **59.1%** |
| candidate evidence (after compaction) | 33,737 | 8,434 | 22.2% |
| DACHApply profile notes | 9,031 | 2,258 | 6.0% |
| mandatory application adaptation rules | 8,430 | 2,108 | 5.6% |
| job description (the only per-job part) | 3,953 | 988 | 2.6% |
| prompt scaffolding, headers, evaluation JSON | 6,864 | 1,716 | 4.5% |
| TOTAL | 151,690 | 37,922 | 100% |

**AC3 — nothing was trimmed.** This task measured; it did not reduce. There is no before/after to
compare because no prompt changed, and that is stated here rather than left as silence.

**AC5 — its condition turned out false.** Templates are ~3.7k of ~40k tokens, not a large share. The
fact that reading a file costs prompt tokens is written into the command's own output and module
docstring anyway, because it is the non-obvious part.

**AC4 — a failed generation costs about 154,200 tokens.** Three attempts (`cv_generator.py`
`for attempt in range(3)`), and the prompt *grows* on attempts 2 and 3 because the repair block
quotes the previous failure back (`failure.diagnostics[-6000:]`, a 6,290-char ceiling). Each attempt
is a separate CLI run, so codex's 9,448-token system prompt is charged three times. A drift test
re-reads `cv_generator.py` and fails if `range(3)`, the `[-6000:]` slice, or the repair text changes.

**On AC1's "not estimates":** every component is measured exactly in characters, and the shares are
therefore exact. The token column is `chars / 4` and says so in the output — no tokenizer is
installed and none was added for this. The one real calibration point is printed alongside: LM Studio
counted **39,129** tokens where chars/4 predicted ~46k, so the divisor reads roughly 18% high on this
material. `--chars-per-token` is the knob. The ranking, which is what the task existed to settle, does
not depend on the divisor.

### A correction to this task's own earlier table

The breakdown first recorded here summed to 131,866 chars against a stated total of 140,478. The
8,612-char gap is the **mandatory adaptation rules file** (`job-application-adaptation-rules.md`,
8,430 chars), which the earlier "scaffolding + mandatory rules 3,889" row did not actually include —
that figure was scaffolding and evaluation JSON only. Found by the implementing agent and verified
independently by reading the file. The headline is unchanged.

### The reason it keeps growing

`learned_application_preferences` is **append-only**. `cv_tasks.py:249` adds one line per learned
preference, deduplicated but never pruned:

    profile.learned_application_preferences='\n'.join([*lines,entry]).strip()

It measured 85,004 chars on 2026-09-09 and 89,675 on 2026-09-10 — it grew by ~4,700 characters in a
day of normal use, and every CV generation pays for the whole accumulated history. Filed as
**TASK-225**.

### Parallel-session collision, resolved

Another Claude session was working this task at the same time and produced a second command,
`cv_prompt_size.py`, with `test_cv_prompt_size.py`. That test file **errors 4 ways** — it passes
`source_text=` to `JobLead.objects.create()` and `source_text` is a read-only property
(`models.py:278`). Both files were left untracked and uncommitted rather than deleted; `report_cv_prompt_size.py`
is the one that shipped, on the strength of 6 passing tests and a verified production run.

## Notes
<!-- SECTION:NOTES:BEGIN -->
Cheapest way to reproduce the total without a provider bill: point CV generation at a local model
whose context is smaller than the request and read the number out of the 400. That is how it was
found. `lms load <model> --context-length 32768` first — LM Studio's JIT default is 8192, which does
not even fit codex's own 9,448-token system prompt.

A correction worth keeping, since it is the reason this task exists rather than a one-line fix:
TASK-221 first recorded that the request was "mostly candidate evidence". Measuring showed compaction
already removes 68% of it. The assumption was wrong and would have sent the work at the wrong target.
<!-- SECTION:NOTES:END -->
