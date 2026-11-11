---
id: TASK-358
title: Choose how many jobs are analysed at the same time
status: In Progress
assignee:
  - '@pi'
created_date: '2026-11-09 16:40'
updated_date: '2026-11-11 09:08'
labels:
  - owner-request
dependencies:
  - TASK-357
modified_files:
  - .pi/STATE.md
  - .orchestrator/debug/01a1c9b7-takeover-baseline-1.md
  - docs/verification-2026-11-11-analysis-queue.md
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
- [x] #1 The Profile page has a slider "Jobs analysed at the same time", 1 to 10 (range to confirm with the owner), default 5, saved per account like the existing daily limits.
- [x] #2 With the setting at N and more than N jobs waiting, exactly N automatic analyses run at once and the rest wait; measured with a test that counts concurrent runs, not argued from code.
- [x] #3 Lowering the setting never cancels runs already going; it applies to the next run that starts. Raising it starts waiting runs without a restart.
- [x] #4 The Queue's time estimates (TASK-340 `_schedule`, currently one fit lane) use N lanes, so "about X min left" stays correct.
- [x] #5 Daily budgets still hold: no more than `daily_analyse_limit` analyses a day whatever N is, and two runs never analyse the same job at once.
- [x] #6 Measured on the owner's machine: with N=5, the real CPU/memory load and the model provider's usage-limit errors stay acceptable over a batch of at least 10 jobs, numbers recorded in the notes. If a local model (ollama/LM Studio) cannot serve 5 at once, the task says so and proposes the fix rather than shipping a default that fails.
- [x] #7 Full backend and frontend suites and typecheck pass.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Preserve Claude state and work on an isolated verification branch based on current origin/main.
2. Recheck lane, daily-budget and Queue-estimate tests.
3. On the owner machine, run at least 10 real provider-backed analyses at N=5 in a disposable database/workspace; measure host CPU/RAM, concurrency and usage-limit errors. Do not mutate production data.
4. Record evidence, fix only demonstrated defects, run full quality gates and evaluate.
5. Commit/push/squash-merge verified changes; mark Done only after all criteria hold.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Owner decided 2026-11-09: range 1-10, and one shared setting for the fit and the requirements analysis.
Ships together with TASK-360 (same files). Adds a Profile field, so a migration: ask the owner before merging.

Risks to check: concurrent model CLI runs hitting the provider's usage limit faster (TASK-317 retries),
local models serving one request at a time, and database connections (Neon pooled).
2026-11-10: merged #380, deployed 64812d1 (migration 0062 applied: health ok), localhost updated. Profile shows the slider (1-10, default 5). Open: AC6, the N=5 CPU/memory/usage-limit measurement over 10+ real analyses; no batch had run yet. Automatic analyses use Codex first (cv_default_choice skips Ollama), so the load is up to 5 Codex CLI processes.

2026-11-11 Pi takeover: real default-provider batch completed on owner machine using a read-only snapshot of ten genuine postings and Profile in disposable SQLite/workspace (no production writes; downstream document admission suppressed). GPT-6.1-Sol/high: 10/10 analyses succeeded in 165.33 s; peak measured simultaneous provider calls 5; usage-limit errors 0. Whole-host CPU mean 16.38%, peak 43.46%; RAM peak used 43.078 GiB / 95.103 GiB, minimum free 52.025 GiB. Backend suite ran concurrently, so these are whole-host observations, not isolated batch attribution. Raw report and 164 samples retained locally in temporary takeover directory; sanitized durable evidence document pending. Focused shared tests: 57 passed.

Verification evidence: docs/verification-2026-11-11-analysis-queue.md. Complete unfiltered backend suite passed (2122 tests; host ERROR_ALERT_EMAILS blanked only for this process); frontend 520 tests and build/typecheck passed. Owner runtime built and rendered; served JavaScript bytes match its dist asset. No application code fix needed. Remains In Progress pending review/evaluation and evidence merge.

Final resource-sample count correction: 163 samples in the completed raw report, not the provisional 164 noted above. The durable verification document has the final measured count.
<!-- SECTION:NOTES:END -->
