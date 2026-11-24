---
id: TASK-407
title: Never change a document that is not ticked
status: In Progress
assignee: []
created_date: '2026-11-24 11:46'
labels: []
dependencies: []
priority: high
ordinal: 412000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner decision 2026-11-24, replaces TASK-278 AC9: an OLD/NEW edit whose text is only in an unticked document no longer changes that document. Reason: the owner chooses which letters and CVs to adjust, if any (TASK-405).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 An exact edit found only in an unticked document (the current one or any other of the job) leaves every unticked file byte-identical and starts no model call
- [ ] #2 Edits found in ticked documents are still applied in the same request
- [ ] #3 The result names how many edits were skipped and in which file
- [ ] #4 Backend pytest, frontend tests and tsc pass; tests shown red on the old code
<!-- AC:END -->
