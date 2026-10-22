---
id: TASK-339
title: >-
  Changed ads of New/Reviewed jobs are accepted; documents are redone only when
  something changed
status: Done
assignee: []
created_date: '2026-10-22 07:35'
updated_date: '2026-10-22 13:25'
labels:
  - backend
dependencies: []
priority: medium
ordinal: 339000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner 2026-10-22 decisions after the TASK-335/336/337 build: changed ads of New/Reviewed jobs -> 'Accept + re-analyse' (newer full ad replaces the stored text automatically, re-analysed within the daily analysis slider; To apply / Ready to submit still stage it, and 'Use fetched' re-analyses). Redo docs -> 'Only if something changed': unreviewed documents are redone only when the ad, the verdict or the application requirements changed; redone documents count against the documents-per-day slider.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Automatic refresh of a New/Reviewed job with a changed full posting accepts it and re-analyses within the daily cap; dismissed copies stay dismissed
- [x] #2 To apply / Ready to submit stage the change; Use fetched re-analyses
- [x] #3 A stale re-check with the same text and same verdict/requirements leaves documents alone
- [x] #4 Changed text/verdict/requirements redoes unreviewed documents within the documents-per-day cap
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Merged #340, deployed. Accept + re-analyse for New/Reviewed changed ads (guard: not thin, not less complete, not dismissed); documents redone only when ad/verdict/requirements changed, counted against the documents slider.
<!-- SECTION:NOTES:END -->
