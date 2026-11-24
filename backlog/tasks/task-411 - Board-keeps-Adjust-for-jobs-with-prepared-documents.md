---
id: TASK-411
title: Board keeps Adjust for jobs with prepared documents
status: Done
assignee: []
created_date: '2026-11-24 16:32'
updated_date: '2026-11-24 16:48'
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
- [x] #1 A job with prepared documents shows an Adjust CV and letters button on the board that opens the generator popup without Generate (as the job page does)
- [x] #2 A job without prepared documents still shows Generate CV and Motivation Letter, unchanged
- [x] #3 npm test and tsc pass; checked in the owner's browser on localhost
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
PR #455 (46a82dd), CI green. Localhost restarted on it 2026-11-24 (bundle index-DV36WJV4.js). Owner's board: 33 jobs with prepared documents; job 1534 shows Adjust CV and letters, its popup has no Generate and has the Adjust section.
<!-- SECTION:NOTES:END -->
