---
id: TASK-265
title: Status 'Ready to submit' for jobs whose CV and/or letter has been generated
status: Done
assignee: []
created_date: '2026-10-05 11:53'
updated_date: '2026-10-05 20:10'
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
- [x] #1 New job status 'documents_ready' labelled 'Documents ready' exists, ordered between 'To apply' and 'Applied', and is included wherever unapplied/actionable statuses are listed (UNAPPLIED_STATUSES, ACTIONABLE_STATUSES, board filters/columns)
- [x] #2 A successful generation (single or bulk) moves a job from new/reviewed/to_apply to documents_ready; it never changes a job that is already applied or later (interview, offer, rejected, ...)
- [x] #3 Existing jobs that already have generated files are moved by a dry-run-by-default management command, not a migration, so the owner can review the list first
- [x] #4 The status can still be set manually and shows with its own badge colour on the board and job page
- [x] #5 Backend tests cover the transition and the no-downgrade rule; revert-to-fail checked
- [x] #6 A board status filter saved in the browser before this change (no ready_to_submit in the list) is upgraded on load so ready_to_submit jobs stay visible (found in browser verification 2026-10-05: generated jobs vanished from the board)
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Owner chose the label 'Ready to submit' (2026-10-05). Use status key 'ready_to_submit' in place of 'documents_ready' in the ACs.

Verified 2026-10-05 on a branch server (127.0.0.1:8010, scratch sqlite + scratch CV workspace, real Codex low-effort generation of 2 jobs): label 'Ready to submit' (key ready_to_submit, owner choice). Real batch moved TNG (reviewed) and Oper (to_apply) to ready_to_submit; applied jobs untouched. Backfill command: dry run listed Oper with its files and wrote nothing; --apply moved only Oper. Teal badge computed light bg rgb(240,253,250)/text rgb(15,118,110), dark rgba(17,94,89,.3)/rgb(153,246,228). Browser verification found saved board filters hid ready_to_submit jobs; fixed by upgradeSavedFilters, re-measured: TNG/Oper back on the board. Backend 1288 passed.

Shipped in #205; production backfill applied 2026-10-05 (13 of 13 moved; re-run dry-run 0).
<!-- SECTION:NOTES:END -->
