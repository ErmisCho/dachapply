---
id: TASK-332
title: A LaTeX compile failure names the actual error
status: Done
assignee: []
created_date: '2026-10-21 15:19'
updated_date: '2026-10-22 13:26'
labels:
  - backend
dependencies: []
priority: medium
ordinal: 332000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Owner 2026-10-21 (screenshot of a Sportradar Readjust: 'LaTeX could not compile the CV.' with Technical details showing hyperref package info): 'fix it'. Measured: the Sportradar CV and letter on disk compile cleanly (pdflatex exit 0); the failing Readjust output was discarded and its temp log is gone. _compile_pdf puts the last 6000 characters of the log into the details, so the box opens on package-loading noise and the '!' error sits at the bottom. The same text feeds the automatic repair prompt.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The failure message names the LaTeX error and its line, e.g. 'LaTeX could not compile the CV: Undefined control sequence (line 123).'
- [x] #2 Technical details start with the error block (the '!' line through the 'l.<n>' line), then the log tail
- [x] #3 A failure with no '!' line says pdflatex stopped without an error message and gives the exit code
- [x] #4 The repair prompt receives the same error-first details
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Merged #331. Live: owner screenshot showed LaTeX could not compile the CV: LaTeX Error: Missing begin-document (line 61) with the error block first, which led to TASK-333.
<!-- SECTION:NOTES:END -->
