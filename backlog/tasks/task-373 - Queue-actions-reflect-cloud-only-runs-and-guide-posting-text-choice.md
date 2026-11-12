---
id: TASK-373
title: Queue actions reflect cloud-only runs and guide posting-text choice
status: In Progress
assignee:
  - '@pi'
created_date: '2026-11-11 17:21'
updated_date: '2026-11-12 11:20'
labels: []
dependencies: []
priority: high
type: bug
ordinal: 376000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Fix the two queue problems reported in the screenshot: cloud retry must not be offered when the active analysis is already cloud-only; jobs blocked on competing posting texts need an actionable route to Keep current / Use fetched, without overwriting either text or retrying the fetch. Preserve useful cloud retry for local-capable and failed runs.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Running fit and requirements analyses already using cloud-only mode do not offer cloud retry; local-capable and failed analyses still offer it.
- [x] #2 A posting-text-choice block offers Choose job text instead of a non-resolving Retry, linking to the existing editor; unrelated blocked states retain their controls.
- [x] #3 Posting-text choice remains explicit: navigating changes neither text, and Keep current / Use fetched still resume preparation through the existing path.
- [x] #4 Regression tests fail on the prior code, pass on the fix, and browser verification plus backend/frontend checks pass without paid model calls or production data changes.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Reproduce the queue/action mismatch and posting-choice dead end; seal rubric and debug evidence. 2. Return accurate cloud retry availability and an explicit posting-choice flag; route to the existing job-text editor without adding another editor. 3. Add focused red/green regressions, verify in a disposable browser runtime, run backend/frontend gates and read-only review. 4. Commit owned files, push and squash-merge after green CI; leave deployment to the owner.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-12: implemented by Codex (headless, worktree), reviewed and verified by Claude.
- Running fit rows publish the run's effective mode as `pipeline.cloud`; requirements runs as `analysing_cloud`. The queue offers cloud retry only when the run is not already cloud-only. Failed analyses keep offering it.
- Blocked rows carry `posting_choice` (the `_gate` condition, `pending_source_text`). The queue renders a "Choose job text" link to `/jobs/<id>` in place of Retry.
- Red/green: 9 new backend cases and 1 frontend case fail on main's source and pass on the fix. Full gates: pytest 2135 passed; tsc clean; vitest 521 passed; `npm run build` ok.
- Browser (headless Chrome, isolated sqlite runtime on :8001/:5199, no model keys): the cloud-only running row has no cloud button, the local row has one, and the posting-choice row shows "Choose job text" with no Retry. A real click opens /jobs/<id>, where Keep current and Use fetched are shown. Both texts were unchanged, and no request other than GET was sent.
- Done waits on merge and on the owner's deploy plus production check (TW-00A steps 4-6).
<!-- SECTION:NOTES:END -->
