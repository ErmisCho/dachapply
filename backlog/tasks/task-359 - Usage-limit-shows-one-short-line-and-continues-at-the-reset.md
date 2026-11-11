---
id: TASK-359
title: Usage limit shows one short line and continues at the reset
status: In Progress
assignee:
  - '@pi'
created_date: '2026-11-09 17:20'
updated_date: '2026-11-11 09:08'
labels:
  - owner-request
dependencies: []
modified_files:
  - .pi/STATE.md
  - .orchestrator/debug/01a1c9b7-takeover-baseline-1.md
  - docs/verification-2026-11-11-analysis-queue.md
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner, 2026-11-09, pasting a failed "Generate CV": "when running out of tokens, summarize the sentence in
one very short message and say when it will be continued and continue on that time".

What the owner saw: a red "Usage limit reached; resets at 19:27." followed by "Technical details" holding
Attempt 1, 230 lines of echoed prompt and the Codex CLI banner/log. The generation then just stops.

Known so far: `cv_tasks` already records `usage_limit` and `reset_at` on a failed task (cv_tasks.py
~582-584), and the document queue retries usage-limited items automatically (TASK-317 `retry_at`). The
manual Generate CV path shown here does not continue by itself.

Also measured today: the owner's Codex quota is shared with Codex PR reviews (CLAUDE.md "Use Codex to
spare Claude tokens", added the same day), so reviews can use up the limit that CV generation needs.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 When any generation (Generate CV, cover letter, queue documents, analyses) hits a provider usage limit, the panel shows one short line, e.g. "Codex limit reached. Continues automatically at 19:27." No raw prompt, banner or log in the default view (Technical details may keep a short provider error, not the echoed prompt).
- [x] #2 The manual Generate CV / letter run is retried automatically at the reset time with the same inputs, without the owner pressing anything, and the line changes to running when it starts. It survives a runtime restart (like TASK-317's `retry_at`).
- [x] #3 The owner can cancel the scheduled continuation from the same panel.
- [x] #4 A limit with no parseable reset time says so ("continues when the limit resets; check back later") and retries on the existing TASK-317 schedule instead of guessing a time.
- [x] #5 Tests: a fake provider returning the real usage-limit text (as pasted above) yields the short line and a scheduled retry that runs at the reset (time patched); the echoed prompt never appears in the API response's error field.
- [x] #6 Verified on localhost with the browser: the short line renders, and the retry fires (reset time patched or a real limit).
- [x] #7 Full backend and frontend suites and typecheck pass.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Verify current retry and restart implementation/tests.
2. Run localhost browser against a disposable SQLite/workspace and a simulated provider limit with accelerated reset; observe short line, cancel control and automatic retry through real endpoints/scheduler.
3. Fix only measured defects with a regression test, run complete suites/build and evaluate.
4. Commit/push/squash-merge evidence or fixes, then complete task in a post-merge administrative change.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Start from cv_tasks' failure path (usage_limit/reset_at) and application_prep's TASK-317 retry_due; reuse
them rather than adding a second scheduler. Do not change which provider/model runs.
2026-11-10: deployed in 64812d1. Open: AC6 browser check needs a real or simulated usage limit.

2026-11-11 Pi takeover: visible Chrome at localhost:8011 against disposable SQLite/workspace passed the simulated-limit browser scenario. Real endpoints, task runner and shared timer: one short line; no prompt/banner in panel; Cancel enabled; same task automatically changed scheduled -> running after accelerated provider reset, with identical input fingerprints; retry cancelled successfully. No browser console errors. Simulation is explicitly not a real provider outage. Screenshots/raw report retained locally; full-suite/evaluation/merge pending.

Final clean browser replay passed, with cancelled worker/model boundary honored. Complete backend 2122 tests, frontend 520 tests and build/typecheck passed. Durable evidence: docs/verification-2026-11-11-analysis-queue.md. Remains In Progress pending review/evaluation and evidence merge.
<!-- SECTION:NOTES:END -->
