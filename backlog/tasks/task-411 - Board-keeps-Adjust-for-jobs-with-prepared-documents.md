---
id: TASK-411
title: Board keeps Adjust for jobs with prepared documents
status: In Progress
assignee: []
created_date: '2026-11-24 16:32'
labels: []
dependencies: []
priority: high
ordinal: 415000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner report 2026-11-24: on the board, new positions offer neither Generate nor Adjust. TASK-392 hides the board's Generate button once a job has prepared documents, and the board's Adjust lives in that popup, so it went too; TASK-392 meant Adjust to remain.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A job with prepared documents shows an Adjust CV and letters button on the board that opens the generator popup without Generate (as the job page does)
- [ ] #2 A job without prepared documents still shows Generate CV and Motivation Letter, unchanged
- [ ] #3 npm test and tsc pass; checked in the owner's browser on localhost
<!-- AC:END -->
