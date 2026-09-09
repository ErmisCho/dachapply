---
id: TASK-224
title: Find out what the 40k-token CV request is actually made of
status: To Do
assignee: []
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

### What is NOT measured, and why

`_compact_candidate_evidence` already removes **68%** of the evidence file, so the obvious suspect is
mostly innocent and the real weight is somewhere else. Candidates, in no particular order:

- the job's `raw_description`, which varies per job and is pasted in whole
- **the LaTeX templates**, which the model pulls in through tool calls — codex reads the files and
  every byte read becomes part of the request. This is the one to check first, because it is the
  only component that grew invisibly: nothing in the prompt shows its size.
- the mandatory adaptation rules and source-priority scaffolding in `_prompt`
- profile notes and learned application preferences

The templates could not be measured from this session: since TASK-99a they are `CvAsset` rows on the
account rather than files on disk, and this session has no production database access. Stating that
rather than guessing at a number.

Note the interaction with TASK-221: a request this size rules out most local models regardless of
their tool support, because the tool-capable ones tend to cap at 32k. Trimming this is the cheapest
route to a free local CV path, if that is still wanted.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The 40,654 tokens are broken down by component with measured numbers, not estimates, and the largest contributor is named
- [ ] #2 The measurement is reproducible on demand — a command or flag that reports the size of a request before it is sent, rather than a number someone recorded once
- [ ] #3 Any reduction is shown to preserve output quality, by generating the same CV for the same job before and after and comparing the documents, not just by asserting the prompt is smaller
- [ ] #4 The retry path is counted: a failed generation's true token cost is stated, given it attempts three times
- [ ] #5 If the templates read through tool calls are a large share, the fact that reading a file costs prompt tokens is written down where the next person will find it
<!-- AC:END -->

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
