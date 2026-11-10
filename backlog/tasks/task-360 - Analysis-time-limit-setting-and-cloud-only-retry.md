---
id: TASK-360
title: Analysis time limit setting and cloud-only retry
status: In Progress
assignee: []
created_date: '2026-11-09 17:45'
labels:
  - owner-request
dependencies:
  - TASK-357
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
- [ ] #7 Verified on localhost in the browser: the setting saves, the stage shows, and the one-time cloud retry runs.
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Adds Profile fields, so a migration: per CLAUDE.md, ask the owner before merging.
2026-11-10: merged #380 (Codex review: literal-edit route also honours cloud-only, test shown failing without the fix). On localhost: the three settings render; a PATCH of the time limit to 7 read back 7 and was restored to 5. Open (AC7): the Finding models stage and the one-time cloud retry were not seen live, because no analysis was running or failed at the time.
<!-- SECTION:NOTES:END -->
