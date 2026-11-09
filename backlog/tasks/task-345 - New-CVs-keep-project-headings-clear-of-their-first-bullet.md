---
id: TASK-345
title: New CVs keep project headings clear of their first bullet
status: Done
assignee: []
created_date: '2026-10-25 15:38'
updated_date: '2026-10-26 10:53'
labels:
  - backend
dependencies: []
priority: medium
ordinal: 345000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found 2026-10-25 on a fresh MP Corporate Finance CV: underlined project names in Selected Projects touch their first bullet. The base CV v1.5 ends \resumeProjectHeading with \vspace{-7pt}; the base PDF shows the same. Owner chose: leave the base files alone, adjust newly generated CVs. Measured on a copy: \vspace{-2pt} clears it and keeps 2 pages.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A newly generated CV whose \resumeProjectHeading ends with \vspace{-7pt} gets \vspace{-2pt} instead; base files untouched; Adjust runs untouched
- [x] #2 Test covers the replacement and that other macros are not changed
- [x] #3 Live: next generated CV shows no heading/bullet contact
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Merged #362. Measured on a compiled copy of the MP Corporate Finance CV: -2pt removes the contact, 2 pages. Base files untouched. Open: AC3 on the next CV the app generates.

2026-10-26: AC3 verified on the first CV generated after the deploy (Eviden/Atos, 11:29): macro at -2pt, all three project headings clear of their first bullet, 2 pages.

2026-10-28 browser live check passed. Generated a fresh CV (Generate, not Adjust/Recompile) for Kraken Software Engineer Autonomous Agents, job 1979, using English base v1.5 and Create CV only. No existing generated files, no replacement, no application submission; job status remains new. Task 954db713b9e74163b90e7b104b1cf898 reached ready. Inspected both PDF pages and an enlarged 216-DPI Selected Projects crop: all 3 project headings clear their first bullets. pdfinfo confirms 2 pages; base template SHA-256 unchanged. PDF left open in Chrome. Spacing/photo regression tests: 4 passed. Frontend build passed. Asian Dad live-check evaluation: PERFECT (self-graded). Full backend gate did not pass: two mail-outbox assertions failed, and the run timed out after 600s at 69%. Both failures reproduced and passed in a diagnostic run with ERROR_ALERT_EMAILS empty; no saved settings or code changed. Evidence and failure investigation: .orchestrator/debug/task-345-live-browser-1.md. The two mail-outbox failures were environmental (ERROR_ALERT_EMAILS set locally); the task stays Done (AC3 was verified 2026-10-26).
<!-- SECTION:NOTES:END -->
