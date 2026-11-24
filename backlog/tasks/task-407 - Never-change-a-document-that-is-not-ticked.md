---
id: TASK-407
title: Never change a document that is not ticked
status: Done
assignee: []
created_date: '2026-11-24 11:46'
updated_date: '2026-11-24 12:58'
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
- [x] #1 An exact edit found only in an unticked document (the current one or any other of the job) leaves every unticked file byte-identical and starts no model call
- [x] #2 Edits found in ticked documents are still applied in the same request
- [x] #3 The result names how many edits were skipped and in which file
- [x] #4 Backend pytest, frontend tests and tsc pass; tests shown red on the old code
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
PR #448, CI green (third run; two earlier runs failed only on the flaky lock tests). 4 tests red on the old code. Stays In Progress until the localhost runtime is updated and checked.

Runtime on 36f35f0 since 2026-11-24, health 200, bundle matches.
<!-- SECTION:NOTES:END -->
