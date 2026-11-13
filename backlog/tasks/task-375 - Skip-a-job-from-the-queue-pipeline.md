---
id: TASK-375
title: Skip a job from the queue pipeline
status: To Do
assignee: []
created_date: '2026-11-13 14:52'
labels: []
dependencies: []
priority: medium
type: feature
ordinal: 377000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The owner can skip a job directly from the Document queue (waiting, running analysis, or blocked), so it stops consuming model time and leaves the pipeline without opening the job.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Every queue row for a job (queued, running analysis, blocked) offers Skip; a running analysis is stopped first.
- [ ] #2 A skipped job leaves the queue and the Blocked list, is marked Not applying (same state as the existing skip decision), and no further analysis or documents start for it.
- [ ] #3 Skip is reversible from the job page; un-skipping does not auto-start work.
- [ ] #4 Tests cover skip for each row state and that no model call starts afterwards; browser-verified on the queue page.
<!-- AC:END -->
