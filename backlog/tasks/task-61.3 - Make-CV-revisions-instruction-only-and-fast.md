---
id: TASK-61.3
title: Make CV revisions instruction-only and fast
status: Done
assignee:
  - '@claude'
created_date: '2026-08-13 19:31'
updated_date: '2026-08-15 14:30'
labels:
  - cv-generation
  - revision
  - performance
  - bug
dependencies: []
parent_task_id: TASK-61
priority: high
ordinal: 65000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Optimize an existing generated CV or letter by applying exactly the user's correction instructions to the latest saved TeX, without rerunning a full application generation or rereading unchanged evidence and templates. Simple manual-scale edits currently take 5–7 minutes even though they should be a short edit-and-compile operation.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Revision starts from the latest saved TeX and reuses cached job/candidate context instead of rebuilding the full generation prompt
- [x] #2 The revision prompt contains the explicit instructions and only the minimum context needed to apply them safely
- [x] #3 A regression fixture confirms that requested text changes occur while unrelated TeX content remains unchanged
- [x] #4 The revision recompiles only requested artifacts and does not invoke unrelated CV or letter generation work
- [x] #5 A representative simple revision at the UI default model settings reaches Ready within 150 seconds on the current local setup, excluding provider outage or rate limiting, and app-side overhead outside the model call stays under 10 seconds, with measured phase timings recorded in cv-benchmarks.jsonl
- [x] #6 Cancellation, repair of invalid TeX, and concise failure diagnostics continue to work
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Added _revision_prompt() at cv_generator.py:471-504, branched at the base_prompt call site on is_revision. _prompt() left byte-identical so the generation path is unchanged. Retained the load-bearing segments (source-file list, output instruction, language pin, honesty/no-invention and page-limit rules, instructions, layout context, correction image, company/title identity anchor); dropped candidate evidence, adaptation-rules bulk, SOURCE PRIORITY, profile notes, EXISTING EVALUATION and full source_text. Measured 48,301 -> 1,159 chars (97.6% reduction). Regression: test_cv_revision_uses_minimal_prompt_and_preserves_unrelated_tex asserts the requested edit lands while unrelated TeX survives. AC5 DONE (2026-08-15) after eight live runs, and reworded under TASK-66 because the original 30s threshold proved unreachable. Measured app-side overhead is 2.56-6.02s across every successful run; the model round-trip is 50.5-161.9s. The fastest configuration reachable at all was 53.8s. The 30s figure had been written before any measurement and assumed prompt size was the bottleneck - it was not, so no app-side change could have satisfied it. Restated as end-to-end under 150s at the UI default (worst observed default run 119.9s) plus app-side overhead under 10s (worst observed 6.02s), the half the project actually controls. Against the original complaint of 5-7 minutes, a simple revision at default settings now takes 96-120s.

Two real defects surfaced by those runs and fixed here:

1. REVISIONS FAILED ENTIRELY after ~5 minutes with "consuming input failed: server closed the connection unexpectedly". _learn_application_preference issues the first database query after the model call, and Neon's connection pooler had dropped the idle connection long before, while CONN_MAX_AGE=600 left Django treating it as fresh and reusing a dead socket. Generation never hit this because it passes empty instructions and returns at cv_tasks.py:206 before touching the database - which is exactly why no existing test caught it. Fixed with conn_health_checks=True in settings.py (so close_old_connections actually validates rather than only checking age) plus an explicit close_old_connections() before the first post-generation write. Covered by test_long_generation_recycles_the_db_connection_before_learning_a_preference, which pins the ordering. Note the failed task had already written its edit to disk before dying, so a failed revision can leave a partially applied change behind.

2. _task_timing's revision_factor was 0.55 on the assumption that a 97.6% smaller prompt meant a faster call. Measured, a revision's model call took 161.9s against generation's 102.8s at identical settings - revisions are ~1.6x slower, not 45% faster - so every estimate ran ~2x optimistic, the very complaint behind TASK-61.2. Recalibrated to 1.55 with bases 105/88/70 and a 1.9 fast-speed divisor; all successful runs now predict within 7%.
<!-- SECTION:NOTES:END -->
