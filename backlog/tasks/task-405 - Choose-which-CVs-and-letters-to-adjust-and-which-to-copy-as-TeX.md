---
id: TASK-405
title: Choose which CVs and letters to adjust and which to copy as TeX
status: In Progress
assignee: []
created_date: '2026-11-23 16:50'
labels: []
dependencies: []
priority: high
ordinal: 406000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner request, 2026-11-23: in CV and letter generation the owner chooses which letters (if any) to adjust and which to copy as TeX. The same for CVs: a job can have two or more. The choices are read from the documents actually present for that job. Today the generator offers one CV tick and one letter tick for adjusting, and Both / CV only / Letter only for copying, so a second CV or a second letter cannot be chosen. Measured 2026-11-23 on the CV workspace: of 141 job entries, 14 have 2 or more CVs on disk (up to 10) and 4 have 3 letters.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The generator (board popup, job page) and each bulk row list every CV, letter and short message whose TeX is on disk for that job, from the server response, with type, language and file name; a document missing on disk is not listed; a job with two CVs shows both
- [ ] #2 Each listed document has its own Adjust tick; Readjust and Recompile write only the ticked documents, and unticked ones stay byte-identical, except that an exact OLD/NEW block found only in the current document of a type with nothing ticked is still applied there (TASK-278 AC9)
- [ ] #3 Several CVs or letters can be adjusted in one go, each with its own language and letter template; one document failing does not stop the others and the error names it
- [ ] #4 Each listed document has its own Copy tick, separate from Adjust; Copy TeX copies exactly the ticked documents in listed order, with the job link line
- [ ] #5 Nothing ticked is possible for both: the button is then disabled and says why; by default the current CV and the current letter are ticked for both
- [ ] #6 The server rejects a document that is not one of this job's own documents on disk (400), and nothing is written or returned for it
- [ ] #7 Existing requests without a document list behave as before (backend pytest, frontend tests and tsc pass)
- [ ] #8 Verified in a real browser on localhost with a job that has two CVs and with one that has several letters
<!-- AC:END -->
