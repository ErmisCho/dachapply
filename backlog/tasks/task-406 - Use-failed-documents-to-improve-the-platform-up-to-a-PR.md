---
id: TASK-406
title: 'Use failed documents to improve the platform, up to a PR'
status: To Do
assignee: []
created_date: '2026-11-23 23:31'
labels: []
dependencies: []
priority: high
ordinal: 407000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner request 2026-11-24: "are you saving the logs of the failed generated files? maybe these can be used autoamticlaly to improve the platform and evne show the process in the platform locally (it would be taking overe with backlog board task, sesion orchestrator, ponytail, asian dad eval)". Owner decisions 2026-11-24: fix up to a PR (the owner merges); a fix starts from a button in the app; the fixing agent may read the full failed files, kept 30 days on this PC only. Measured 2026-11-24: 16 of 137 Adjusts since 2026-10-21 failed, all with a reason in adjustments.jsonl, 5 with TeX and log. Rejected model answers and failed first generations without a LaTeX error keep no files. The TASK-372 collector is off (ERROR_OCCURRENCE_LOCAL_DB unset) and groups documents by task id with class unknown, so it could never file a bug.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 All subtasks are Done
- [ ] #2 One real failure was followed end to end on localhost: saved, grouped, shown, fixed by a started run, and left as a PR that was not merged by the run
<!-- AC:END -->
