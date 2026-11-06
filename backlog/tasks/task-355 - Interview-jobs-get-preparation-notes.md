---
id: TASK-355
title: Interview jobs get preparation notes
status: Done
assignee: []
created_date: '2026-11-06 16:30'
labels:
  - owner-request
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner: moved two jobs to Interview and got no option for notes. Owner chose: moving a job to Interview gives preparation notes for that job.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Moving a job into Interview starts prep notes for it with no further action, as one model run that respects Pause and shows in the queue.
- [x] #2 Jobs already in Interview get a visible option to generate prep notes.
- [x] #3 The notes appear on the job page and are reachable from the Interview row.
- [x] #4 The notes are grounded in the posting, the evaluation and the candidate profile, and cover what to study and likely questions.
- [x] #5 A failure shows inline with a retry, and refreshing or moving the job again does not generate a duplicate.
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Verified on the real runtime with a fake model: moving a job to Interview made one model call, held while stopped and ran on Resume. Refreshing and moving out and back made no second call. A failure showed inline, and Retry produced the note. Interview rows link to the notes. The panel can lag about 15 s behind the API.
<!-- SECTION:NOTES:END -->
