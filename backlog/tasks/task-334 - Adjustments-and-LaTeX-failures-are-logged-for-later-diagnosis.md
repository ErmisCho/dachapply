---
id: TASK-334
title: Adjustments and LaTeX failures are logged for later diagnosis
status: Done
assignee: []
created_date: '2026-10-21 15:45'
updated_date: '2026-10-21 16:02'
labels:
  - backend
dependencies: []
priority: medium
ordinal: 334000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner 2026-10-21, after a Sportradar Adjust failed and its broken TeX was gone: 'you should be logging these adjustments and error, so you can solve them later'. Today a failed run leaves nothing: the compile happens in a temp dir that is deleted, the task lives only in memory, and relaunch.log is overwritten on every relaunch. Logs stay on this machine inside the private CV workspace (they hold CV text and instructions); nothing goes to the database.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Every Adjust (revise-latest) request appends one JSON line to <CODEX_CV_WORKSPACE>/.dachapply-logs/adjustments.jsonl: time, job id, company, title, route (no-change, exact OLD/NEW, literal, local model, full optimization, fallback reason), model, the full instructions, final status, error summary and diagnostics head
- [x] #2 Every failed pdflatex compile (any path) keeps a copy of the failing .tex and its .log in <workspace>/.dachapply-logs/failed/ named with time and file name, and the log line points to them
- [x] #3 Logging never fails or slows the task: errors writing the log are swallowed and logged at debug
- [x] #4 Old entries are not deleted automatically (no rotation yet; ponytail note)
- [x] #5 Tests cover a successful exact edit, a failed compile with saved files, and a logging write error
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Merged #335. Live: a no-change Adjust on job 1825 wrote one line to C:\latex\.dachapply-logs\adjustments.jsonl (route no-change, status ready); CV files untouched.
<!-- SECTION:NOTES:END -->
