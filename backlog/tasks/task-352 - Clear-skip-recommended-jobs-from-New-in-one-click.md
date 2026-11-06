---
id: TASK-352
title: Clear skip-recommended jobs from New in one click
status: To Do
assignee: []
created_date: '2026-11-06 12:30'
labels:
  - owner-review
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner approved after a measured review: 28 of 65 New jobs are recommended skip.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A single board action targets only status new jobs whose latest evaluation recommends skip.
- [ ] #2 The owner sees the list of affected jobs and must confirm before anything changes.
- [ ] #3 Confirming moves exactly those jobs to skipped, with no model call and no document generation.
- [ ] #4 Only the owner's own jobs can be changed.
<!-- AC:END -->
