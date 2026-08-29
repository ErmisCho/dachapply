---
id: TASK-201
title: Make the follow-up sent-date assertion timezone-stable
status: Done
assignee:
  - '@pi'
created_date: '2026-08-29 22:03'
updated_date: '2026-08-29 22:14'
labels:
  - backend
  - bug
  - ci
dependencies: []
modified_files:
  - backend/jobradar/tests/test_api.py
  - .orchestrator/debug/task-201-2026-08-29-bugfix-1-1.md
priority: high
type: bug
ordinal: 201000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Main CI fails after local midnight because the follow-up audit note intentionally records the configured local date while its test compares the UTC date of sent_at. Align the assertion with the user-visible local-date behavior so CI is stable across the UTC/local midnight boundary.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The follow-up audit note continues to record the configured local calendar date
- [x] #2 The test compares sent_at in the configured timezone rather than its raw UTC date
- [x] #3 The focused regression and full CI pass across the UTC/local-date boundary
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Record the exact CI/local boundary failure and trace production date semantics. 2. Change only the test assertion to convert sent_at through Django's configured timezone before taking its date. 3. Rerun the focused regression while UTC and local dates differ, then full CI. 4. Merge, confirm Azure deploy resumes, close TASK-201, and finalize.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Reproduced both in GitHub Actions run 33277441723 and locally after 22:00 UTC: the note says 2026-08-30 (Europe/Vienna) while followup.sent_at.date() says 2026-08-29 (UTC). Production correctly uses timezone.localdate(); the test's raw UTC date assertion is the defect.

Changed only the failing assertion to compare timezone.localtime(followup.sent_at).date() with the local-date audit note. The focused regression passed during the live UTC/Vienna date split (1 passed); production behavior is unchanged.

PR #97 squash-merged as 602d4994f44d48f3056a13b8323ace987a0f2327. The pull-request suite and post-merge main suite both passed during the live UTC/Vienna date split; Azure deployment and public-app verification resumed successfully in run 33277866780. Local runtime, origin/main, and Azure now share 602d4994.

Asian Dad evaluation: PERFECT (self-graded). All four sealed criteria passed using the reproduced boundary failure, local focused pass, unfiltered pull-request/main CI passes, and successful deployment evidence.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Made the follow-up sent-date assertion convert the stored UTC timestamp to Django's configured timezone before comparing its calendar date, preserving correct production notes and eliminating the daily midnight flake. Verified by focused reproduction at the boundary, full PR/main CI, and successful Azure deployment.
<!-- SECTION:FINAL_SUMMARY:END -->
