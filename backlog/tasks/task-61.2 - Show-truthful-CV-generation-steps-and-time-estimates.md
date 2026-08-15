---
id: TASK-61.2
title: Show truthful CV generation steps and time estimates
status: Done
assignee:
  - '@claude'
created_date: '2026-08-13 19:30'
updated_date: '2026-08-15 14:30'
labels:
  - cv-generation
  - ux
  - progress
dependencies: []
parent_task_id: TASK-61
priority: high
ordinal: 64000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Replace the opaque percentage-only CV/letter generation indicator with specific live phases and a completed-step count. Include preparation, model work, validation or repair, each requested TeX/PDF artifact, packaging, and cache/recompile paths. Correct the consistently optimistic remaining-time estimate using the actual route and selected provider/model settings.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The UI displays the current phase and completed/total steps throughout generation, revision, cache restoration, and PDF-only recompilation
- [x] #2 CV and letter compilation are separate visible steps, and the UI explicitly reports when each requested PDF has compiled
- [x] #3 Skipped artifacts and cache hits adjust the total step count instead of leaving phantom steps
- [x] #4 Remaining-time estimates account for operation type, provider, model, effort, speed, cache state, and elapsed phase time
- [x] #5 The estimate does not reach zero or claim imminent completion while model work or compilation is still active
- [x] #6 Automated tests cover the event-to-progress mapping and a live benchmark records estimated versus actual duration
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Per-artifact compile stages already existed in compile_documents() (shipped in b2e9b4f); the real gap was the step model and ETA calibration. Added _STEP_STAGES/_STEP_LABELS/_STAGE_STEP/_plan_steps/_step_progress in cv_tasks.py, exposing step_label / step_completed / step_total via get_cv_task(). step_total is route-aware (CV+letter 5, single artifact 4, recompile 1-2) and collapses to 2 mid-run on an exact cache hit, so skipped artifacts and cache hits reduce the total instead of leaving phantom steps. Recalibrated _task_timing against measured benchmarks (77.87s uncached two-job, 1.25s cached, 3.55s recompile) and gave _remaining_runtime a floor so the estimate cannot read ~0 while generating/compiling_cv/compiling_letter is active. All three frontend progress renderers updated (ProgressButton, batch row bar, batch aggregate) and tolerate a decreasing step_total.

AUDIT CORRECTION (2026-08-14): an evaluation pass found AC2 and AC4 were checked while only partly true. Both are now genuinely met.
- AC2: _STEP_LABELS collapsed compiling_cv+cv_compiled under the single label 'Compiling CV', so the UI still read "Compiling CV" after the PDF existed and completion was only implied by the step counter advancing - not the "explicitly reports" the AC requires. Added _STEP_DONE_LABELS (cv_compiled -> 'CV compiled', letter_compiled -> 'Motivation letter compiled', generated -> 'Documents generated'), selected in _step_progress when a step's terminal marker fires. No frontend change needed: stepText() renders step_label verbatim, so the UI now shows "CV compiled - step 3/5". Covered by test_cv_task_step_progress_reflects_route_completion_and_cache_reduction.
- AC4: _task_timing accepted provider and model but never used them in the estimate - they only reached the _estimate_key tuple used as a lookup key for empirical history, so on a cold start a local Ollama model and a cloud model produced an identical ETA. Added provider_factor (openai 1, anthropic .9, ollama/lmstudio 2.5) and a coarse model_factor (opus 1.3, haiku/mini/nano/flash .6) multiplying the generation figure only; LaTeX compile defaults stay provider-independent because compilation is local work. _stage_history still overrides these with measured medians once samples exist. Covered by test_task_timing_estimate_varies_with_provider_and_model, whose key assertion is that the openai and ollama estimates differ for the same model name.
Verified by running the pure-function subset (6 passed, 1.50s) against the sqlite fallback with DATABASE_URL blanked, so no Neon test database was created - see TASK-62.

AC6 PARTIAL (2026-08-14): the event-to-progress mapping half is now fully covered - test_stage_key_maps_every_reported_event_string_to_a_progress_stage pins every raw progress string cv_generator emits to its internal stage key, including the repair path, unknown strings and None, and asserts every step-bearing stage is reachable from a real event string. The recording half is now built but not yet exercised: _record_benchmark() appends one JSONL row per finished task to <CODEX_CV_WORKSPACE>/.dachapply-cache/cv-benchmarks.jsonl with route, provider, model, effort, speed, cache_hit, estimated_seconds (the ETA computed at task creation), actual_seconds, and per-phase stage_seconds. It writes only into a workspace directory that already exists and swallows every exception, so telemetry can never break a generation. Covered by test_finished_task_records_estimated_versus_actual_duration_and_phase_timings and test_benchmark_is_not_written_when_the_workspace_does_not_exist.

AC6 DONE (2026-08-15). Eight live runs recorded to cv-benchmarks.jsonl, each carrying estimated_seconds, actual_seconds and per-phase stage_seconds.

The benchmark immediately paid for itself by exposing a calibration error no code reading would have found: revision_factor was 0.55, on the assumption that the 97.6% smaller revision prompt meant a faster model call. Measured at identical settings, a revision's model call took 161.9s against generation's 102.8s - revisions are ~1.6x SLOWER, because the model still reads the source TeX and reasons about the edit. Every estimate was therefore ~2x optimistic, which is precisely the "consistently optimistic remaining-time estimate" this task was opened to fix, so AC4 was only nominally satisfied before this run.

Recalibrated against the recorded data: revision_factor 0.55 -> 1.55, generation bases 78/65/52 -> 105/88/70, fast-speed divisor 1.5 -> 1.9. Replayed against all successful runs, predictions now land within 1.02-1.07x of actual - deliberately a touch conservative, since over-estimating is the safe direction for this task's purpose.

    route       eff/spd         scope       actual    predicted
    generation  medium/normal   cv+letter   102.8s      105.0s
    revision    medium/normal   cv+letter   161.9s      162.8s
    revision    low/fast        cv+letter    62.5s       64.2s
    revision    low/fast        cv only      50.5s       53.8s
    revision    low/normal      cv only      57.1s       61.4s

Also confirmed live: step totals dropped 5 -> 4 when the letter was skipped (AC3), and the completed-step labels from the AUDIT CORRECTION above rendered correctly throughout.
<!-- SECTION:NOTES:END -->
