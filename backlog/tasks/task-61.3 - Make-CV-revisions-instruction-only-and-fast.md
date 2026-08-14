---
id: TASK-61.3
title: Make CV revisions instruction-only and fast
status: In Progress
assignee:
  - '@claude'
created_date: '2026-08-13 19:31'
updated_date: '2026-08-14 16:05'
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
- [ ] #5 A representative simple revision reaches Ready within 30 seconds on the current local setup, excluding provider outage or rate limiting, with measured phase timings recorded
- [x] #6 Cancellation, repair of invalid TeX, and concise failure diagnostics continue to work
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Added _revision_prompt() at cv_generator.py:471-504, branched at the base_prompt call site on is_revision. _prompt() left byte-identical so the generation path is unchanged. Retained the load-bearing segments (source-file list, output instruction, language pin, honesty/no-invention and page-limit rules, instructions, layout context, correction image, company/title identity anchor); dropped candidate evidence, adaptation-rules bulk, SOURCE PRIORITY, profile notes, EXISTING EVALUATION and full source_text. Measured 48,301 -> 1,159 chars (97.6% reduction). Regression: test_cv_revision_uses_minimal_prompt_and_preserves_unrelated_tex asserts the requested edit lands while unrelated TeX survives. AC5 NOT verified: no live provider was available in the agent sandbox, so the <30s wall-clock measurement is still outstanding. The recording it needs now exists (2026-08-14): every finished task appends estimated_seconds, actual_seconds and per-phase stage_seconds to <CODEX_CV_WORKSPACE>/.dachapply-cache/cv-benchmarks.jsonl, with route='revision' for this path - see TASK-61.2 notes.

REMAINING FOR AC5: run one representative simple revision against a live provider and read the row back from cv-benchmarks.jsonl; it passes if actual_seconds < 30. No code work is expected unless the measurement comes in over 30s.
<!-- SECTION:NOTES:END -->
