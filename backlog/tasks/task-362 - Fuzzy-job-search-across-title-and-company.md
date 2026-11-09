---
id: TASK-362
title: Fuzzy job search across title and company
status: To Do
assignee: []
created_date: '2026-11-09 19:30'
labels:
  - owner-request
dependencies:
  - TASK-361
priority: medium
ordinal: 362000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner, 2026-11-09: "make it that i can search for a job listing based on a fuzzy version of a job listing,
title, company, like now I can't find the zuelhle advanced data Engineer positon for some reason".

Cause in code (not yet measured against the owner's data): the board's search box sends one string and
`JobLeadViewSet` filters `company__icontains=s | title__icontains=s | original_source_text__icontains=s | ...`
(`backend/jobradar/views.py`, `p.get('search')`). The whole phrase must appear verbatim inside one field, so
"zuelhle advanced data engineer" cannot match company "Zühlke" + title "(Senior) Advanced Data Engineer":
the words span two fields, "ü" is typed as "ue", and "zuelhle" is a typo of "zuehlke".
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Each word of the query is matched separately and all must match somewhere in company, title, location or the posting, so a query mixing company and title words finds the job.
- [ ] #2 Umlauts and their spellings are equivalent in both directions: "zuehlke", "zuhlke" and "Zühlke" find the same jobs; likewise ä/ae, ö/oe, ß/ss; case is ignored.
- [ ] #3 A small typo in a company or title word still matches (e.g. "zuelhle" finds Zühlke, "enginer" finds Engineer), ranked below exact matches, without matching unrelated jobs: a test with at least 20 realistic jobs shows no false hit for 5 typo queries.
- [ ] #4 The owner's real case works: on localhost, "zuelhle advanced data engineer" finds the Zühlke Advanced Data Engineer job; recorded with the job id in the notes.
- [ ] #5 Search stays fast: one board request with a search on the owner's real board (measured job count recorded) answers within 500 ms on localhost, and does not add a database query per job.
- [ ] #6 Existing filters (company, location, skill, status) and board ordering behave as before; full backend and frontend suites and typecheck pass.
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Not yet measured: whether the Zühlke job exists under that exact title on the owner's board. Check that first;
if it is missing rather than unfindable, that is a separate finding.
<!-- SECTION:NOTES:END -->
