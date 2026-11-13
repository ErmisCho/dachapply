---
id: TASK-377
title: One blocked or stalled job never holds up the rest of the queue
status: To Do
assignee: []
created_date: '2026-11-13 15:35'
labels: []
dependencies: []
priority: high
type: bug
ordinal: 379000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner request 2026-11-13: if one job in the queue is blocked, the others continue. Blocked jobs (waiting for the owner) already stay out of the run queue; this task proves that with a regression test and removes the remaining single-job stalls, e.g. a hung analysis occupying the only analysis slot until the 5-minute limit. An account-wide provider usage limit may still pause all work, and the queue says so.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Regression test: with one job blocked (text choice, missing posting, failed analysis), other jobs' analyses and documents start and finish.
- [ ] #2 A stalled analysis (no progress) releases its slot early enough that the next job starts; measured in a test, not estimated.
- [ ] #3 When an account-wide usage limit pauses everything, the queue states that it is a provider limit affecting all jobs and when it resumes.
- [ ] #4 Existing ordering, Move to front, cancel/skip (TASK-375/376) and time-limit behaviour stay green; browser-verified with one blocked job and others progressing.
<!-- AC:END -->
