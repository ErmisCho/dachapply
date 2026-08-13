---
id: TASK-61.3
title: Make CV revisions instruction-only and fast
status: To Do
assignee: []
created_date: '2026-08-13 19:31'
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
- [ ] #1 Revision starts from the latest saved TeX and reuses cached job/candidate context instead of rebuilding the full generation prompt
- [ ] #2 The revision prompt contains the explicit instructions and only the minimum context needed to apply them safely
- [ ] #3 A regression fixture confirms that requested text changes occur while unrelated TeX content remains unchanged
- [ ] #4 The revision recompiles only requested artifacts and does not invoke unrelated CV or letter generation work
- [ ] #5 A representative simple revision reaches Ready within 30 seconds on the current local setup, excluding provider outage or rate limiting, with measured phase timings recorded
- [ ] #6 Cancellation, repair of invalid TeX, and concise failure diagnostics continue to work
<!-- AC:END -->
