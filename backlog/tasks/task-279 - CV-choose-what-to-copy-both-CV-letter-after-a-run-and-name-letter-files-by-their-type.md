---
id: TASK-279
title: >-
  CV: choose what to copy (both, CV, letter) after a run, and name letter files
  by their type
status: In Progress
assignee: []
created_date: '2026-10-12 14:35'
updated_date: '2026-10-13 06:56'
labels: []
dependencies: []
ordinal: 275000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner request 2026-10-12: 'maybe I can select afterwards if I want to copy both tex files or only cv or only letter. Also the filenames for letters should show what they are in the filename, so not have letter in the name rather than Motivationsschreiben for Motivationsschreiben files'. Today Copy TeX always copies every document of the run. Letters generated before TASK-253 (2026-09-28) are named '<applicant>-Letter-<target>' and a revision keeps that name, so e.g. the Techsearch Motivationsschreiben was written today as Chorinopoulos-Ermis-Letter-Techsearch-Ai-Developerin.tex (93 such files in C:/latex/output).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 After a run that has both a CV and a letter, the Copy TeX control lets the owner pick Both, CV only or Letter only; each copies exactly that TeX with the TASK-250 job-link comment line
- [ ] #2 With only one document in the run, Copy TeX copies it directly with no extra choice
- [ ] #3 The automatic copy when a run finishes still copies every document of the run (unchanged)
- [ ] #4 The bulk generation panel's per-row Copy TeX offers the same choice
- [ ] #5 A revision or compile of a letter whose filename still carries the generic 'Letter' label renames its .tex and .pdf to the letter template's label (e.g. Motivationsschreiben, Anschreiben, English-Motivation-Letter) through the TASK-271 rename path, updating the job's tracking so later revisions find it
- [ ] #6 The rename never overwrites an existing file and never renames a letter the owner named themselves (TASK-271 preferred name)
- [ ] #7 Backend and frontend tests cover the copy choice and the legacy-letter rename; full backend suite, frontend tests and tsc pass
- [ ] #8 Verified on localhost: copy each choice on a real job and see the clipboard content; revise a legacy-named letter and see the renamed files on disk
- [ ] #9 A rename (automatic or owner-chosen) also moves the LaTeX helper files beside the TeX (.aux, .log, .fls, .fdb_latexmk, .out, .synctex.gz) so no file keeps the old name; a helper whose new name is taken is left in place, never overwritten, and never blocks the rename
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-13 owner request after localhost check: 'can you fix those' -- BEKO's rename left Letter-named .aux/.log/.fls/.fdb_latexmk files behind in C:/latex/output.
<!-- SECTION:NOTES:END -->
