---
id: TASK-358
title: Choose how many jobs are analysed at the same time
status: To Do
assignee: []
created_date: '2026-11-09 16:40'
labels:
  - owner-request
dependencies:
  - TASK-357
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner, 2026-11-09: "maybe I can set up with a slider how many jobs I want analysed at the same time, with 5
being the default".

Today automatic analyses run strictly one at a time: `application_prep._pipeline_lock` (a single `Lock`)
plus `processing_control.ControlStore.claim`, which allows one running unit across `pipeline` and
`daily-document`. On 2026-11-08/09 that left 24 jobs waiting (TASK-357 covers the hang that caused it).
Documents already have their own parallelism (`settings.PREP_QUEUE_CONCURRENCY`), which this does not
change.

Depends on TASK-357: both touch `_pipeline`, and parallel runs must keep its 10-minute limit per run.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The Profile page has a slider "Jobs analysed at the same time", 1 to 10 (range to confirm with the owner), default 5, saved per account like the existing daily limits.
- [ ] #2 With the setting at N and more than N jobs waiting, exactly N automatic analyses run at once and the rest wait; measured with a test that counts concurrent runs, not argued from code.
- [ ] #3 Lowering the setting never cancels runs already going; it applies to the next run that starts. Raising it starts waiting runs without a restart.
- [ ] #4 The Queue's time estimates (TASK-340 `_schedule`, currently one fit lane) use N lanes, so "about X min left" stays correct.
- [ ] #5 Daily budgets still hold: no more than `daily_analyse_limit` analyses a day whatever N is, and two runs never analyse the same job at once.
- [ ] #6 Measured on the owner's machine: with N=5, the real CPU/memory load and the model provider's usage-limit errors stay acceptable over a batch of at least 10 jobs, numbers recorded in the notes. If a local model (ollama/LM Studio) cannot serve 5 at once, the task says so and proposes the fix rather than shipping a default that fails.
- [ ] #7 Full backend and frontend suites and typecheck pass.
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Open questions for the owner before building: slider range (1-10 suggested), and whether the requirements
analysis (`daily-document`) shares the same N or stays at one.

Risks to check: concurrent model CLI runs hitting the provider's usage limit faster (TASK-317 retries),
local models serving one request at a time, and database connections (Neon pooled).
<!-- SECTION:NOTES:END -->
