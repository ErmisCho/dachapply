---
id: TASK-265
title: Status 'Ready to submit' for jobs whose CV and/or letter has been generated
status: To Do
assignee: []
created_date: '2026-10-05 11:53'
updated_date: '2026-10-05 11:59'
labels: []
dependencies: []
priority: medium
ordinal: 263000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner wants jobs with a generated CV and/or letter to show a distinct, professional status (e.g. 'Documents ready' rather than 'ready to apply'). Today STATUSES has new/reviewed/to_apply/applied/... and nothing marks that documents exist. Adding a choice needs a migration: merge it promptly (see memory: committing a migration breaks the live board).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 New job status 'documents_ready' labelled 'Documents ready' exists, ordered between 'To apply' and 'Applied', and is included wherever unapplied/actionable statuses are listed (UNAPPLIED_STATUSES, ACTIONABLE_STATUSES, board filters/columns)
- [ ] #2 A successful generation (single or bulk) moves a job from new/reviewed/to_apply to documents_ready; it never changes a job that is already applied or later (interview, offer, rejected, ...)
- [ ] #3 Existing jobs that already have generated files are moved by a dry-run-by-default management command, not a migration, so the owner can review the list first
- [ ] #4 The status can still be set manually and shows with its own badge colour on the board and job page
- [ ] #5 Backend tests cover the transition and the no-downgrade rule; revert-to-fail checked
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Owner chose the label 'Ready to submit' (2026-10-05). Use status key 'ready_to_submit' in place of 'documents_ready' in the ACs.
<!-- SECTION:NOTES:END -->
