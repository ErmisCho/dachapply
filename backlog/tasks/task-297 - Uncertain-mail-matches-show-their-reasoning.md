---
id: TASK-297
title: Uncertain mail matches show their reasoning
status: To Do
assignee: []
created_date: '2026-10-14 21:44'
labels: []
dependencies: []
ordinal: 298000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner (2026-10-14): when the app is not 100% sure an email belongs to a job (e.g. two Hays jobs exist), it must say so and why instead of linking silently or presenting a bare suggestion.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Every suggested or auto-attached match carries a short reason (same thread / sender names company X / subject names title Y / only job at company)
- [ ] #2 When more than one job is plausible, the suggestion is marked 'unsure' and lists the candidates with why each was considered; it is never auto-attached
- [ ] #3 The reason is shown next to the suggestion on the Mailbox page, in the re-check list and on the auto-attached badge
- [ ] #4 Tests cover reason text for each rule and the unsure multi-candidate case
<!-- AC:END -->
