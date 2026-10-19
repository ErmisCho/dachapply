---
id: TASK-322
title: >-
  Fetched postings are checked for tasks, requirements, salary and company
  description
status: Done
assignee: []
created_date: '2026-10-19 18:53'
updated_date: '2026-10-19 20:13'
labels:
  - backend
  - frontend
dependencies: []
priority: high
ordinal: 322000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner 2026-10-19: after analysing from a job link, check the text really contains what is gathered every time. Measured: a headless render of a Workday URL returned the career-site search page, not an ad. Owner chose: required parts = tasks, requirements, salary, company description; check by keyword rule after fetch AND by the AI during analysis; if missing, try other ways (headless re-read) first, then flag + hold documents.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A keyword check (German + English wording) reports which of tasks, requirements, salary, company description a posting text lacks
- [x] #2 After a fetch whose text lacks a required part, the page is re-read with the headless browser (when available) and the more complete text is kept
- [x] #3 The evaluation (model and paste paths, prompt + schema) also reports the missing parts; the AI result overrides the keyword result once the job is analysed; the owner's saved evaluation template keeps working
- [x] #4 A job whose posting still lacks a required part is flagged on the board (which parts) and its documents are held: the Queue lists it as blocked 'Posting incomplete: missing ...' with Continue anyway (prepare despite gaps, remembered for that job) and Retry (re-fetch)
- [x] #5 Pasting a complete text on the job page clears the flag and lets documents proceed
- [x] #6 Tests cover the keyword check, the headless re-read choice, the AI field, the hold/continue path, each failing when its logic is removed; vitest/tsc; CI green
- [x] #7 Verified on localhost on a real job
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Verified on localhost 2026-10-19 (PR #310): 31 board rows show 'Posting incomplete' with the missing parts in the tooltip; the headless re-read turned ÖBB 1847's 1368-char API text into the full 7053-char ad; the AI reported missing_parts [] on re-analysis. Continue anyway is covered by tests; no job was held at verification time to click it.
<!-- SECTION:NOTES:END -->
