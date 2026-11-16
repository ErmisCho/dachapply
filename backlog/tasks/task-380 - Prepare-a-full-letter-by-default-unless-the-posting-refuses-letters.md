---
id: TASK-380
title: Prepare a full letter by default unless the posting refuses letters
status: In Progress
assignee: []
created_date: '2026-11-16 14:12'
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
- [ ] #1 plan_variants: absent / not_mentioned / optional letter requirements give cv + full letter per language; cover_letter not_accepted gives no full letter; required/preferred and unclear behave as before
- [ ] #2 LETTER_RULE says a full letter is prepared unless the posting says letters are not accepted, and the panel shows it
- [ ] #3 Backend and frontend suites green in CI; changed tests red on origin/main
<!-- AC:END -->
