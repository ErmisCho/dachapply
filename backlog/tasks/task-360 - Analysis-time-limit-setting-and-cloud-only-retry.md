---
id: TASK-360
title: Analysis time limit setting and cloud-only retry
status: In Progress
assignee:
  - '@pi'
created_date: '2026-11-09 17:45'
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
Owner, 2026-11-09, after TASK-357: "make it that you are able to set the time ... to 5 minutes and also be
able to show it in the progress bars and make it that I can restart and bypass this (so I would use the
cloud models)". Clarified by the owner the same day:
- the 5 minutes is the whole automatic-analysis limit (TASK-357's `ANALYSIS_TIME_LIMIT`, now a fixed 600 s);
- bypass means two choices: "Use cloud models only" (always) and "Use cloud models only this time".

Cloud models = the Codex/Claude CLI providers; local = Ollama / LM Studio, found by
`cv_generator._discover_model_options` (the step that hung in TASK-357).

Couple with TASK-358 (same files: application_prep, Profile settings, Queue) and ship them together.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The Profile page has "Time limit for one analysis" in minutes, default 5, saved per account; both automatic analyses (fit, requirements) use it instead of the fixed 600 s, and the timeout wording shows the configured minutes.
- [x] #2 The Queue shows the model-finding step as its own stage ("Finding models") for a running analysis, before Fetching/Analysing, with its elapsed time.
- [x] #3 The Profile page has a switch "Use cloud models only": when on, automatic analyses and generation skip local model discovery entirely (no `ollama`/`lms` process is started) and use the cloud default.
- [x] #4 A stuck (running) or failed analysis in the Queue offers "Use cloud models only this time": it stops the current run if any, and re-runs that one job with cloud models without changing the switch.
- [x] #5 If no cloud model is available, both cloud options say so plainly instead of failing silently.
- [x] #6 Tests cover each AC above; each new test fails with its change reverted. Full backend and frontend suites and typecheck pass.
- [x] #7 Verified on localhost in the browser: the setting saves, the stage shows, and the one-time cloud retry runs.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Verify current timeout, cloud-only and model-stage implementation/tests.
2. In a disposable localhost browser runtime, save/reload settings, simulate stuck model discovery, click one-time cloud retry and observe replacement analysis while Profile switch remains unchanged.
3. Fix only measured defects, run complete suites/build and evaluate.
4. Commit/push/squash-merge evidence or fixes, then complete task in a post-merge administrative change.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Adds Profile fields, so a migration: per CLAUDE.md, ask the owner before merging.
2026-11-10: merged #380 (Codex review: literal-edit route also honours cloud-only, test shown failing without the fix). On localhost: the three settings render; a PATCH of the time limit to 7 read back 7 and was restored to 5. Open (AC7): the Finding models stage and the one-time cloud retry were not seen live, because no analysis was running or failed at the time.

2026-11-11 Pi takeover: visible Chrome at localhost:8011 passed: Profile time limit 5 -> 7, saved/reloaded at 7, restored 5; default concurrency slider 5, bounds 1-10. Forced uncached model discovery to block in disposable runtime: Queue displayed Finding models and 0:29 elapsed. Clicked Use cloud models only this time; real queue endpoint cancelled/replaced the run, canned cloud analysis completed in 3.074 s, Profile cloud switch remained false. Provider model answer/discovery block were simulated; real pipeline/importer/endpoints/UI were exercised. Focused shared tests: 57 passed. Full-suite/evaluation/merge pending.

Final clean browser replay: one replacement provider entry; one-time cloud retry completed in 3.069 s, time limit restored to 5. Complete backend 2122 tests, frontend 520 tests and build/typecheck passed. Durable evidence: docs/verification-2026-11-11-analysis-queue.md. Remains In Progress pending review/evaluation and evidence merge.
<!-- SECTION:NOTES:END -->
