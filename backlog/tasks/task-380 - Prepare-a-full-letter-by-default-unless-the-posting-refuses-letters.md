---
id: TASK-380
title: Prepare a full letter by default unless the posting refuses letters
status: Done
assignee: []
created_date: '2026-11-16 14:12'
updated_date: '2026-11-16 16:16'
labels:
  - backend
dependencies: []
priority: medium
ordinal: 382000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner, 2026-11-16: 'make it always, most of the jobs want it' (after Capgemini Technical Gen AI Solutions Consultant got only a CV). plan_variants gave letters only for required/preferred; now a posting that does not mention a letter, or calls it optional, also gets a full letter. Not accepted still means none.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 plan_variants: absent / not_mentioned / optional letter requirements give cv + full letter per language; cover_letter not_accepted gives no full letter; required/preferred and unclear behave as before
- [x] #2 LETTER_RULE says a full letter is prepared unless the posting says letters are not accepted, and the panel shows it
- [x] #3 Backend and frontend suites green in CI; changed tests red on origin/main
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Verified on localhost 2026-11-16 (7640567, logged in): job 2063 shows per-document Adjust toggles; choosing one shows "Adjust only this", both shows "Adjust these 2" and the shared box; job 1897 (CV only, status new) shows Prepare letter; the panel shows the new letter rule. No generation was started for the check.
<!-- SECTION:NOTES:END -->
